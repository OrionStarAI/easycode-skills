#!/usr/bin/env ruby
# frozen_string_literal: true

# Synchronize opted-in skills from their public GitHub source. The workflow
# runs this script on a temporary branch and opens a review PR; it never writes
# directly to object storage or publishes a Marketplace release.

require "fileutils"
require "open3"
require "pathname"
require "psych"
require "set"
require "tmpdir"

ROOT = File.expand_path("..", __dir__)
SKILLS_ROOT = File.join(ROOT, "skills")

class SyncError < StandardError; end

MISSING_FRONTMATTER_VALUE = Object.new.freeze

def parse_yaml(yaml)
  Psych.safe_load(
    yaml,
    permitted_classes: [],
    permitted_symbols: [],
    aliases: false
  )
rescue ArgumentError
  Psych.safe_load(yaml, [], [], false)
end

def parse_frontmatter(path)
  lines = File.binread(path).force_encoding("UTF-8").lines
  raise "frontmatter must start with ---" unless lines.first&.strip == "---"
  closing = lines[1..]&.index { |line| line.strip == "---" }
  raise "frontmatter closing delimiter is missing" unless closing
  data = parse_yaml(lines[1, closing].join)
  raise "frontmatter must be a YAML mapping" unless data.is_a?(Hash)
  data
rescue Psych::Exception => e
  raise "invalid YAML frontmatter: #{e.message.to_s.lines.first.to_s.strip}"
end

# Return the parsed frontmatter and the untouched body. Upstream skills do not
# own the marketplace-only keys that we add locally (category, tags, upstream,
# author, etc.), so a normal line-based git merge can report a conflict even
# when the actual changes are independent. Keep this helper deliberately
# conservative: if either side cannot be parsed, the caller falls back to the
# existing git merge and leaves the conflict visible for review.
def frontmatter_parts(bytes)
  text = bytes.dup.force_encoding("UTF-8")
  return nil unless text.valid_encoding?

  lines = text.lines
  return nil unless lines.first&.strip == "---"

  closing = lines[1..]&.index { |line| line.strip == "---" }
  return nil unless closing

  data = parse_yaml(lines[1, closing].join)
  return nil unless data.is_a?(Hash)

  [data, lines[(closing + 1)..]&.join.to_s]
rescue Psych::Exception
  nil
end

def merge_frontmatter_values(base, local, upstream)
  keys = []
  [local, upstream, base].each do |values|
    values.each_key { |key| keys << key unless keys.include?(key) }
  end

  merged = {}
  keys.each do |key|
    base_value = base.key?(key) ? base[key] : MISSING_FRONTMATTER_VALUE
    local_value = local.key?(key) ? local[key] : MISSING_FRONTMATTER_VALUE
    upstream_value = upstream.key?(key) ? upstream[key] : MISSING_FRONTMATTER_VALUE

    value = if local_value == base_value
              upstream_value
            elsif upstream_value == base_value
              local_value
            elsif local_value == upstream_value
              local_value
            else
              return nil
            end
    merged[key] = value unless value.equal?(MISSING_FRONTMATTER_VALUE)
  end
  merged
end

# Merge independently changed frontmatter fields while preserving the body
# from whichever side changed it. This handles the common case where upstream
# bumps `version` and the marketplace adds local metadata to the same header.
# If both sides changed the body, return nil so git merge-file can provide the
# normal three-way conflict for human review.
def semantic_skill_text_merge(local_bytes, base_bytes, upstream_bytes)
  local = frontmatter_parts(local_bytes)
  base = frontmatter_parts(base_bytes)
  upstream = frontmatter_parts(upstream_bytes)
  return nil unless local && base && upstream

  merged_frontmatter = merge_frontmatter_values(base[0], local[0], upstream[0])
  return nil unless merged_frontmatter

  body = if local[1] == base[1]
           upstream[1]
         elsif upstream[1] == base[1]
           local[1]
         elsif local[1] == upstream[1]
           local[1]
         else
           return nil
         end

  yaml = Psych.dump(merged_frontmatter).sub(/\A---\s*\n/, "")
  "---\n#{yaml}---\n#{body}"
end

def git_output(directory, *args)
  stdout, stderr, status = Dir.chdir(directory || ROOT) { Open3.capture3("git", *args) }
  return stdout if status.success?

  message = stderr.to_s.strip
  raise SyncError, "git #{args.join(" ")} failed#{message.empty? ? "" : ": #{message}"}"
end

def git_capture(directory, *args)
  Dir.chdir(directory || ROOT) { Open3.capture3("git", *args) }
end

def relative_files(directory, ref, source_root)
  prefix = source_root.sub(%r{/\z}, "")
  command_args = ["ls-tree", "-r", "--name-only", ref]
  # A dot means that the upstream skill lives at the repository root. Git
  # does not prefix root-level paths with "./", so list the complete tree in
  # that case instead of filtering for a literal dot path.
  command_args += ["--", prefix] unless prefix == "." || prefix.empty?
  files = git_output(directory, *command_args).lines.map(&:chomp)
  return files.reject(&:empty?) if prefix == "." || prefix.empty?

  files.each_with_object([]) do |path, result|
    next if path.empty?
    if path == prefix
      result << File.basename(path)
    elsif path.start_with?("#{prefix}/")
      result << path[(prefix.length + 1)..]
    end
  end
end

def bytes_for(path)
  File.binread(path)
end

def binary_bytes?(bytes)
  bytes.include?("\0")
end

def safe_join(root, relative)
  # `upstreamPath: .` is a valid root. Normalize it before comparing the
  # expanded child path; otherwise a root ending in `/.` makes every file
  # look like it escaped the repository (for example `.gitattributes`).
  root = File.expand_path(root)
  path = File.expand_path(relative, root)
  unless path == root || path.start_with?("#{root}#{File::SEPARATOR}")
    raise SyncError, "refusing path outside repository: #{relative.inspect}"
  end
  path
end

def write_bytes(path, bytes)
  FileUtils.mkdir_p(File.dirname(path))
  File.binwrite(path, bytes)
end

def normalize_for_conflict(bytes)
  value = bytes.dup.force_encoding("UTF-8")
  value = value.encode("UTF-8", invalid: :replace, undef: :replace)
  value.end_with?("\n") ? value : "#{value}\n"
end

def conflict_text(local_bytes, upstream_bytes, upstream_ref)
  [
    "<<<<<<< local",
    normalize_for_conflict(local_bytes),
    "=======",
    normalize_for_conflict(upstream_bytes),
    ">>>>>>> upstream/#{upstream_ref}",
    ""
  ].join("\n")
end

def update_upstream_sha(path, sha)
  text = File.binread(path).force_encoding("UTF-8")
  lines = text.lines
  closing = lines[1..]&.index { |line| line.strip == "---" }
  raise SyncError, "#{path} has no frontmatter closing delimiter" unless closing

  replacement = "upstreamSha: #{sha}\n"
  existing = (1...closing).find { |index| lines[index].match?(/\A\s*upstreamSha\s*:/) }
  if existing
    lines[existing] = replacement
  else
    lines.insert(closing, replacement)
  end
  File.binwrite(path, lines.join)
end

def write_github_outputs(changed, conflicts)
  output_path = ENV["GITHUB_OUTPUT"]
  return unless output_path && !output_path.empty?

  File.open(output_path, "a") do |file|
    file.puts("changed=#{changed}")
    file.puts("conflicts=#{conflicts}")
  end
end

def run_self_test
  Dir.mktmpdir("easycode-skill-sync-self-test-") do |root|
    root_with_dot = File.join(root, ".")
    expected = File.join(root, ".gitattributes")
    actual = safe_join(root_with_dot, ".gitattributes")
    raise "root-relative path was not normalized" unless actual == expected

    begin
      safe_join(root_with_dot, "../outside")
      raise "path traversal was not rejected"
    rescue SyncError
      # Expected: safe_join must reject paths outside the repository root.
    end
  end

  base = <<~YAML
    ---
    name: sample
    description: "Sample skill"
    version: 1.0.0
    ---

    base body
  YAML
  local = <<~YAML
    ---
    name: sample
    description: "Sample skill"
    version: 1.0.0
    category: 视频创作
    upstream: example/skills
    ---

    base body
  YAML
  upstream = <<~YAML
    ---
    name: sample
    description: "Sample skill"
    version: 1.1.0
    ---

    upstream body
  YAML
  merged = semantic_skill_text_merge(local, base, upstream)
  raise "semantic frontmatter merge did not resolve independent changes" unless merged
  merged_data, = frontmatter_parts(merged)
  raise "upstream version was not selected" unless merged_data["version"] == "1.1.0"
  raise "local category was not preserved" unless merged_data["category"] == "视频创作"
  raise "local upstream metadata was not preserved" unless merged_data["upstream"] == "example/skills"
  raise "upstream body was not selected" unless merged.end_with?("upstream body\n")
  puts "[self-test] safe_join root normalization and traversal guard passed"
end

if ARGV.delete("--self-test")
  run_self_test
  exit 0
end

targets = []
Dir[File.join(SKILLS_ROOT, "*", "SKILL.md")].sort.each do |skill_path|
  metadata = parse_frontmatter(skill_path)
  next unless metadata["upstream"]

  skill_dir = File.dirname(skill_path)
  targets << {
    name: File.basename(skill_dir),
    path: skill_path,
    dir: skill_dir,
    remote: metadata["upstream"],
    source_root: metadata["upstreamPath"],
    base_sha: metadata["upstreamSha"]
  }
end

if targets.empty?
  puts "No skills have upstream sync metadata; nothing to do."
  write_github_outputs(false, false)
  exit 0
end

changed_count = 0
conflict_count = 0

Dir.mktmpdir("easycode-skill-sync-") do |temporary_root|
  targets.group_by { |target| target[:remote] }.each do |remote, remote_targets|
    remote_key = remote.gsub(%r{[^A-Za-z0-9_.-]}, "_")
    current_dir = File.join(temporary_root, "#{remote_key}-current")
    repository_url = "https://github.com/#{remote}.git"
    git_output(nil, "clone", "--depth", "1", "--no-tags", repository_url, current_dir)
    current_sha = git_output(current_dir, "rev-parse", "HEAD").strip
    base_dirs = {}

    remote_targets.each do |target|
      if target[:base_sha] == current_sha
        puts "#{target[:name]}: already at #{current_sha[0, 12]}"
        next
      end

      unless target[:base_sha].is_a?(String) && target[:base_sha].match?(/\A[0-9a-f]{7,64}\z/i)
        raise SyncError, "#{target[:name]} has an invalid upstreamSha"
      end

      base_dir = base_dirs[target[:base_sha]]
      unless base_dir
        base_dir = File.join(temporary_root, "#{remote_key}-base-#{target[:base_sha][0, 12]}")
        git_output(nil, "clone", "--no-tags", "--no-checkout", repository_url, base_dir)
        git_output(base_dir, "fetch", "--no-tags", "origin", target[:base_sha], "--depth=1")
        git_output(base_dir, "checkout", "--detach", target[:base_sha])
        base_dirs[target[:base_sha]] = base_dir
      end

      source_files = relative_files(current_dir, "HEAD", target[:source_root])
      base_files = relative_files(base_dir, "HEAD", target[:source_root])
      if source_files.empty?
        raise SyncError, "#{target[:name]}: no files found at upstreamPath #{target[:source_root].inspect}"
      end

      source_set = source_files.to_set
      base_set = base_files.to_set
      skill_conflict = false
      skill_changed = false

      source_files.each do |relative|
        source_path = safe_join(File.join(current_dir, target[:source_root]), relative)
        local_path = safe_join(target[:dir], relative)
        base_path = safe_join(File.join(base_dir, target[:source_root]), relative)
        source_bytes = bytes_for(source_path)

        unless File.file?(local_path)
          write_bytes(local_path, source_bytes)
          skill_changed = true
          next
        end

        local_bytes = bytes_for(local_path)
        next if local_bytes == source_bytes

        if File.file?(base_path) && local_bytes == bytes_for(base_path)
          write_bytes(local_path, source_bytes)
          skill_changed = true
          next
        end

        if binary_bytes?(local_bytes) || binary_bytes?(source_bytes) || (File.file?(base_path) && binary_bytes?(bytes_for(base_path)))
          # Binary assets have no meaningful three-way merge. The upstream
          # version wins, while local-only assets remain untouched.
          write_bytes(local_path, source_bytes)
          skill_changed = true
          next
        end

        if File.file?(base_path)
          semantic = relative == "SKILL.md" && semantic_skill_text_merge(local_bytes, bytes_for(base_path), source_bytes)
          if semantic
            write_bytes(local_path, semantic)
            skill_changed = true
          else
            merged, _stderr, status = git_capture(nil, "merge-file", "-p", local_path, base_path, source_path)
            raise SyncError, "#{target[:name]}: git merge-file failed for #{relative}" if status.exitstatus && status.exitstatus > 1
            write_bytes(local_path, merged)
            skill_changed = true
            skill_conflict = true if status.exitstatus == 1
          end
        else
          write_bytes(local_path, conflict_text(local_bytes, source_bytes, current_sha))
          skill_changed = true
          skill_conflict = true
        end
      end

      # Apply upstream deletions only when the local copy is still identical
      # to the recorded base. Locally edited files are retained and reported.
      (base_set - source_set).each do |relative|
        local_path = safe_join(target[:dir], relative)
        base_path = safe_join(File.join(base_dir, target[:source_root]), relative)
        next unless File.file?(local_path) && File.file?(base_path)

        if bytes_for(local_path) == bytes_for(base_path)
          File.delete(local_path)
          skill_changed = true
        else
          skill_conflict = true
          warn "#{target[:name]}: upstream deleted locally modified file #{relative}; retained local copy"
        end
      end

      if skill_changed && !skill_conflict
        update_upstream_sha(target[:path], current_sha)
      end
      changed_count += 1 if skill_changed
      conflict_count += 1 if skill_conflict
      puts "#{target[:name]}: #{skill_conflict ? "conflict" : "updated"} -> #{current_sha[0, 12]}" if skill_changed
    end
  end
end

changed = changed_count.positive?
conflicts = conflict_count.positive?
write_github_outputs(changed, conflicts)
puts "Upstream sync finished: #{changed_count} skill(s) changed, #{conflict_count} conflict(s)."
