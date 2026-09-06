#!/usr/bin/env ruby
# frozen_string_literal: true

# A dependency-free gate for the published skill source tree.
#
# The gate intentionally parses SKILL.md frontmatter with a real YAML parser
# instead of trying to validate it with regular expressions. This catches
# errors such as an unquoted ": " inside a description before a release.

require "json"
require "pathname"
require "psych"

ROOT = File.expand_path("..", __dir__)
SKILLS_ROOT = File.join(ROOT, "skills")
MAX_PREVIEWS = 4
MAX_EXAMPLES = 3
MAX_TEXT_SCAN_BYTES = 10 * 1024 * 1024

def relative_path(path)
  Pathname.new(path).relative_path_from(Pathname.new(ROOT)).to_s
end

def issue(issues, path, message)
  issues << "#{relative_path(path)}: #{message}"
end

def parse_yaml(yaml)
  Psych.safe_load(
    yaml,
    permitted_classes: [],
    permitted_symbols: [],
    aliases: false
  )
rescue ArgumentError
  # Compatibility with the older Psych API shipped with some developer Macs.
  Psych.safe_load(yaml, [], [], false)
end

def parse_frontmatter_text(text)
  lines = text.lines
  raise "file must start with a YAML frontmatter delimiter (---)" unless lines.first&.strip == "---"

  closing_index = lines[1..]&.index { |line| line.strip == "---" }
  raise "frontmatter closing delimiter (---) is missing" unless closing_index

  frontmatter = lines[1, closing_index].join
  data = parse_yaml(frontmatter)
  raise "frontmatter must be a YAML mapping" unless data.is_a?(Hash)

  [data, closing_index + 1]
rescue Psych::Exception => e
  first_line = e.message.to_s.lines.first.to_s.strip
  raise "invalid YAML frontmatter: #{first_line}"
end

def parse_frontmatter(path)
  parse_frontmatter_text(File.binread(path).force_encoding("UTF-8")).first
end

def non_empty_string?(value)
  value.is_a?(String) && !value.strip.empty?
end

def safe_relative_asset?(path)
  return false unless path.is_a?(String) && !path.empty?
  pathname = Pathname.new(path)
  !pathname.absolute? && !path.split("/").include?("..") && !path.include?("\0")
end

def check_asset(issues, skill_dir, value, label)
  unless value.is_a?(Hash)
    issue(issues, skill_dir, "#{label} must be an object")
    return
  end

  path = value["path"]
  unless safe_relative_asset?(path)
    issue(issues, skill_dir, "#{label}.path must be a safe relative path")
    return
  end

  full_path = File.expand_path(path, skill_dir)
  unless full_path == skill_dir || full_path.start_with?("#{skill_dir}#{File::SEPARATOR}")
    issue(issues, skill_dir, "#{label}.path escapes the skill directory")
  end
  issue(issues, full_path, "#{label}.path does not exist") unless File.file?(full_path)
end

def check_asset_list(issues, skill_dir, media, key, max)
  values = media[key]
  return if values.nil?

  unless values.is_a?(Array)
    issue(issues, skill_dir, "media.#{key} must be an array")
    return
  end
  issue(issues, skill_dir, "media.#{key} contains more than #{max} entries") if values.length > max
  values.each_with_index { |value, index| check_asset(issues, skill_dir, value, "media.#{key}[#{index}]") }
end

def validate_manifest(issues, skill_dir, skill_name)
  path = File.join(skill_dir, "marketplace.json")
  unless File.file?(path)
    issue(issues, path, "marketplace.json is required")
    return
  end

  manifest = JSON.parse(File.read(path))
rescue JSON::ParserError => e
  issue(issues, path, "invalid JSON: #{e.message}")
  return
else
  unless manifest["schemaVersion"] == 1
    issue(issues, path, 'schemaVersion must be 1')
  end

  skill = manifest["skill"]
  unless skill.is_a?(Hash)
    issue(issues, path, "skill must be an object")
    return
  end

  issue(issues, path, "skill.name must be #{skill_name.inspect}") unless skill["name"] == skill_name
  issue(issues, path, "skill.version must be a non-empty string") unless non_empty_string?(skill["version"])
  issue(issues, path, "skill.source must be a non-empty string") unless non_empty_string?(skill["source"])
  %w[active deleted].each do |key|
    issue(issues, path, "skill.#{key} must be boolean") if skill.key?(key) && ![true, false].include?(skill[key])
  end
  if skill.key?("usageExample") && !skill["usageExample"].nil? && !non_empty_string?(skill["usageExample"])
    issue(issues, path, "skill.usageExample must be a non-empty string or null")
  end

  issue(issues, path, "skill.displayName is required (bilingual zh/en)") unless skill.key?("displayName")

  %w[displayName description].each do |key|
    next unless skill.key?(key)

    value = skill[key]
    unless value.is_a?(Hash) && non_empty_string?(value["zh"]) && non_empty_string?(value["en"])
      issue(issues, path, "skill.#{key} must be an object with non-empty zh and en strings")
      next
    end
    issue(issues, path, "skill.#{key}.zh must contain Chinese characters") unless value["zh"].match?(/\p{Han}/)
    issue(issues, path, "skill.#{key}.en must contain Latin letters (translate, don't copy the slug)") unless value["en"].match?(/[A-Za-z]/)
  end

  storage = manifest["storage"]
  unless storage.is_a?(Hash) && non_empty_string?(storage["packageKey"])
    issue(issues, path, "storage.packageKey must be a non-empty string")
  end

  media = manifest["media"]
  unless media.is_a?(Hash)
    issue(issues, path, "media must be an object")
    return
  end

  check_asset(issues, skill_dir, media["icon"], "media.icon") if media.key?("icon") && !media["icon"].nil?
  check_asset_list(issues, skill_dir, media, "previews", MAX_PREVIEWS)
  check_asset_list(issues, skill_dir, media, "previewThumbnails", MAX_PREVIEWS)
  check_asset_list(issues, skill_dir, media, "examples", MAX_EXAMPLES)

  previews = media["previews"]
  thumbnails = media["previewThumbnails"]
  if previews.is_a?(Array) && thumbnails.is_a?(Array) && !previews.empty? && thumbnails.length != previews.length
    issue(issues, path, "media.previewThumbnails must match media.previews in length")
  end
end

def validate_frontmatter(issues, path, skill_name)
  text = File.binread(path).force_encoding("UTF-8")
  data, = parse_frontmatter_text(text)

  name = data["name"]
  description = data["description"]
  issue(issues, path, "name must be a non-empty string") unless non_empty_string?(name)
  issue(issues, path, "description must be a non-empty string") unless non_empty_string?(description)
  issue(issues, path, "name must match the directory #{skill_name.inspect}") if non_empty_string?(name) && name != skill_name
  issue(issues, path, "name must use kebab-case") if non_empty_string?(name) && name !~ /\A[a-z0-9]+(?:-[a-z0-9]+)*\z/

  if data.key?("tags") && !(
    (data["tags"].is_a?(Array) && data["tags"].all? { |tag| non_empty_string?(tag) }) ||
    (data["tags"].is_a?(String) && !data["tags"].strip.empty?)
  )
    issue(issues, path, "tags must be a non-empty string or an array of strings")
  end

  upstream_keys = %w[upstream upstreamPath upstreamSha]
  if upstream_keys.any? { |key| data.key?(key) }
    upstream_keys.each do |key|
      issue(issues, path, "#{key} is required when upstream sync is configured") unless non_empty_string?(data[key])
    end
    if non_empty_string?(data["upstream"]) && data["upstream"] !~ /\A[^\/\s]+\/[^\/\s]+\z/
      issue(issues, path, "upstream must be in owner/repository form")
    end
    if non_empty_string?(data["upstreamPath"])
      source_path = data["upstreamPath"]
      unless safe_relative_asset?(source_path)
        issue(issues, path, "upstreamPath must be a safe relative path")
      end
    end
    if non_empty_string?(data["upstreamSha"]) && data["upstreamSha"] !~ /\A[0-9a-f]{7,64}\z/i
      issue(issues, path, "upstreamSha must be a hexadecimal commit SHA")
    end
  end

  data
rescue StandardError => e
  issue(issues, path, e.message)
  nil
end

def likely_secret?(text)
  patterns = [
    /(?:ghp|github_pat)_[A-Za-z0-9_]{30,}/,
    /\bglpat-[A-Za-z0-9_-]{20,}\b/,
    /\bAKIA[0-9A-Z]{16}\b/,
    /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
    /\bAIza[0-9A-Za-z_-]{30,}\b/,
    /\bsk-[A-Za-z0-9]{20,}\b/
  ]
  patterns.any? { |pattern| text.match?(pattern) }
end

def scan_for_secrets(issues)
  ignored_parts = %w[.git node_modules]
  Dir.glob(File.join(ROOT, "**", "*"), File::FNM_DOTMATCH).each do |path|
    next unless File.file?(path)
    relative = relative_path(path)
    next if ignored_parts.any? { |part| relative.split(File::SEPARATOR).include?(part) }
    next if File.size(path) > MAX_TEXT_SCAN_BYTES

    bytes = File.binread(path)
    next if bytes.include?("\0")
    text = bytes.force_encoding("UTF-8")
    next unless text.valid_encoding?
    if likely_secret?(text)
      issue(issues, path, "possible credential/token detected; remove it before merging")
    end
    if text.match?(/^<<<<<<< /) || text.match?(/^>>>>>>> /)
      issue(issues, path, "merge conflict markers detected")
    end
  rescue Errno::EACCES, Errno::ENOENT
    # A disappearing or unreadable file is not a secret finding.
  end
end

def run_self_test
  bad = <<~YAML
    ---
    name: remotion-best-practices
    description: Comprehensive Remotion video-creation guidance: project setup, React compositions
    ---
  YAML
  begin
    parse_frontmatter_text(bad)
    abort "[self-test] expected the unquoted description colon to fail"
  rescue StandardError => e
    abort "[self-test] unexpected parser failure: #{e.message}" unless e.message.include?("invalid YAML frontmatter")
  end

  good = <<~YAML
    ---
    name: remotion-best-practices
    description: "Comprehensive Remotion video-creation guidance: project setup, React compositions"
    ---
  YAML
  data, = parse_frontmatter_text(good)
  abort "[self-test] quoted description did not parse" unless data["description"].include?(": project")
  puts "[self-test] YAML frontmatter colon guard passed"
end

run_self_test if ARGV.delete("--self-test")

issues = []
skill_dirs = Dir[File.join(SKILLS_ROOT, "*")].select { |path| File.directory?(path) && !File.symlink?(path) }.sort
issue(issues, SKILLS_ROOT, "no skill directories found") if skill_dirs.empty?

names = {}
skill_dirs.each do |skill_dir|
  skill_name = File.basename(skill_dir)
  skill_path = File.join(skill_dir, "SKILL.md")
  unless File.file?(skill_path)
    issue(issues, skill_path, "SKILL.md is required")
    next
  end
  metadata = validate_frontmatter(issues, skill_path, skill_name)
  if metadata && non_empty_string?(metadata["name"])
    if names.key?(metadata["name"])
      issue(issues, skill_path, "duplicate skill name; already declared in #{relative_path(names[metadata["name"]])}")
    else
      names[metadata["name"]] = skill_path
    end
  end
  manifest = validate_manifest(issues, skill_dir, skill_name)

  # The marketplace renders the SKILL.md description unless the manifest declares
  # a curated bilingual skill.description. An English-leading SKILL.md description
  # therefore requires the manifest override, or the listing shows English only.
  if non_empty_string?(metadata["description"]) && !metadata["description"].match?(/\p{Han}/)
    manifest_path = File.join(skill_dir, "marketplace.json")
    if manifest.is_a?(Hash)
      skill = manifest["skill"]
      declared = skill.is_a?(Hash) && skill.key?("description")
    else
      declared = File.file?(manifest_path) && begin
        parsed = JSON.parse(File.read(manifest_path))
        parsed.is_a?(Hash) && parsed["skill"].is_a?(Hash) && parsed["skill"].key?("description")
      rescue JSON::ParserError
        false
      end
    end
    unless declared
      issue(issues, skill_path,
            "SKILL.md description has no Chinese characters; declare a bilingual skill.description in marketplace.json to localize the listing")
    end
  end
end

scan_for_secrets(issues)

if issues.empty?
  puts "Skill gate passed: #{skill_dirs.length} skill(s), #{names.length} unique name(s)."
  exit 0
end

warn "Skill gate failed with #{issues.length} issue(s):"
issues.each { |entry| warn "  - #{entry}" }
exit 1
