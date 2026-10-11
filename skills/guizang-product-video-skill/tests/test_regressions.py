"""Offline regressions for delivery gates and headless-only preflight."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import shutil
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
delivery=module('check_delivery');environment=module('check_environment')
class Delivery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        (self.root/'evidence.md').write_text('Release evidence fixture')
        (self.root/'DIRECTION.md').write_text('# 方向\n因为产品是模型选择器，所以镜头推近选择器。\n| # | 镜头 |\n|---|---|\n| 1 | feature |\n')
        self.plan={'demo':False,'style':'repo','duration':5,'fps':30,'width':1920,'height':1080,'audioRequired':False,'audioExceptionReason':'User requested a silent version',
            'voiceoverRequired':False,'voiceoverExceptionReason':'User requested a silent version',
            'motion':{'uiEffects':True,'cameraMove':True},
            'typography':{'mode':'bilingual','zhStyle':'sans-serif','zhFont':'Noto Sans CJK','enFont':'Georgia'},
            'shots':[{'id':'feature','start':0,'end':5,'type':'detail','headline':'切换模型，继续对话','headlineEn':'Switch models','claim':True,'source':['file:evidence.md'],
                'plainExplanation':'切换模型后，可以带着之前的对话继续工作。','description':'切换模型后，对话内容会保留。','component':'src/selector.tsx','actions':[]}]}
    def errors(self):return delivery.check(self.plan,project_dir=self.root)['errors']
    def test_valid_production(self):self.assertEqual(self.errors(),[])
    def test_all_claims_false(self):
        self.plan['shots'][0]['claim']=False;self.assertTrue(any('at least one' in x for x in self.errors()))
    def test_demo_still_allowed(self):
        self.plan['demo']=True;self.plan['shots'][0]['claim']=False;self.assertEqual(self.errors(),[])
    def test_feature_components_required(self):
        for kind in ['detail','workspace','macro']:
            for value in [None,'','   ']:
                with self.subTest(kind=kind,value=value):
                    self.plan['shots'][0].update(type=kind,component=value)
                    self.assertTrue(any('component source' in x for x in self.errors()))
    def test_audio_exception_required(self):
        for value in [None,'','   ',True]:
            self.plan['audioExceptionReason']=value
            self.assertTrue(any('audioExceptionReason' in x for x in self.errors()))
    def test_source_files_resolve(self):
        for source in ['file:missing.md','./missing.md','repo:missing.tsx']:
            self.plan['shots'][0]['source']=[source];self.assertTrue(self.errors())
        self.plan['repo']=str(self.root)
        for source in ['repo:evidence.md:2','file:evidence.md#L3','evidence.md']:
            self.plan['shots'][0]['source']=[source];self.assertEqual(self.errors(),[])
    def test_legacy_paths_search_video_then_repo(self):
        repo=self.root/'product';(repo/'src/components').mkdir(parents=True)
        (repo/'src/components/Selector.jsx').write_text('export const Selector = 1;')
        (repo/'CHANGELOG.md').write_text('Product release')
        self.plan['repo']='product'
        self.plan['shots'][0]['source']=['src/components/Selector.jsx:12','CHANGELOG.md#L2']
        self.assertEqual(self.errors(),[])
        self.assertEqual(delivery.source_file('CHANGELOG.md',self.root,'product'),repo/'CHANGELOG.md')
        (self.root/'CHANGELOG.md').write_text('Video evidence')
        self.assertEqual(delivery.source_file('CHANGELOG.md',self.root,'product'),self.root/'CHANGELOG.md')
        self.plan['shots'][0]['source']=['missing.md'];self.assertTrue(self.errors())
    def test_explicit_source_roots_do_not_fall_back(self):
        repo=self.root/'product';repo.mkdir();(repo/'release.md').write_text('Release')
        self.plan['repo']=str(repo)
        for source in ['file:release.md','./release.md','../release.md']:
            self.plan['shots'][0]['source']=[source];self.assertTrue(self.errors())
        self.plan['shots'][0]['source']=['repo:release.md'];self.assertEqual(self.errors(),[])
        self.assertEqual(delivery.source_file(str(repo/'release.md'),self.root,None),repo/'release.md')
    def test_production_requires_direction(self):
        (self.root/'DIRECTION.md').unlink()
        self.assertTrue(any('DIRECTION.md' in x for x in self.errors()))
        self.plan['demo']=True;self.assertFalse(any('DIRECTION.md' in x for x in self.errors()))
    def test_direction_without_reasons_warns(self):
        (self.root/'DIRECTION.md').write_text('| # | 镜头 |\n|---|---|\n| 1 | feature |\n')
        warnings=delivery.check(self.plan,project_dir=self.root)['warnings']
        self.assertTrue(any('derive devices' in w for w in warnings))
    def test_external_evidence_not_treated_as_file(self):
        self.plan['shots'][0]['source']=['https://example.org/release.md','tag:v1.0','commit:abc123'];self.assertEqual(self.errors(),[])
    def test_voiceover_exception_required(self):
        self.plan['voiceoverRequired']=False
        for value in [None,'','   ']:
            self.plan['voiceoverExceptionReason']=value
            self.assertTrue(any('voiceoverExceptionReason' in x for x in self.errors()))
    def test_voiceover_needs_file_and_lines(self):
        self.plan['voiceoverRequired']=True
        self.assertTrue(any('audio.voiceover.file' in x for x in self.errors()))
        self.plan['audio']={'voiceover':{'file':'assets/voice/voiceover.wav','lines':[]}}
        self.assertTrue(any('audio.voiceover.lines' in x for x in self.errors()))
    def test_voiceover_line_outside_its_shot_warns(self):
        self.plan['voiceoverRequired']=True
        self.plan['audio']={'voiceover':{'file':'assets/voice/voiceover.wav','lines':[
            {'shot':'feature','at':4.0,'duration':2.5,'text':'切换模型后，对话会保留。','file':'assets/voice/line-01.wav'}]}}
        result=delivery.check(self.plan,project_dir=self.root)
        self.assertEqual(result['errors'],[])
        self.assertTrue(any('shot' in w and ('outside' in w or 'longer' in w) for w in result['warnings']))
    def test_motion_exception_required(self):
        self.plan['motion']={'uiEffects':True,'cameraMove':False}
        self.assertTrue(any('motion.exceptionReason' in x for x in self.errors()))
    def test_shot_camera_move_conflicts_with_user_choice(self):
        self.plan['motion']={'uiEffects':True,'cameraMove':False,'exceptionReason':'User asked for a static camera'}
        self.plan['shots'][0]['motion']={'camera':'push-in'}
        self.assertTrue(any('camera move the user declined' in x for x in self.errors()))
    def test_missing_motion_and_narration_only_warn(self):
        # Plans made before these questions existed must keep passing; the reminder is a warning.
        del self.plan['motion']
        del self.plan['voiceoverRequired']
        del self.plan['voiceoverExceptionReason']
        result=delivery.check(self.plan,project_dir=self.root)
        self.assertEqual(result['errors'],[])
        self.assertTrue(any('plan.motion' in item for item in result['warnings']))
        self.assertTrue(any('voiceoverRequired' in item for item in result['warnings']))


def mean_volume(path):
    output=subprocess.run(['ffmpeg','-hide_banner','-i',str(path),'-af','volumedetect','-f','null','-'],capture_output=True,text=True).stderr
    for line in output.splitlines():
        if 'mean_volume' in line:return float(line.split('mean_volume:')[1].strip().split()[0])
    raise AssertionError('volumedetect reported no mean_volume')


class VoiceMix(unittest.TestCase):
    """Exercises the real narrated mix path, which the plan-only checks cannot cover."""
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg needed for the narrated mix regression')
    def test_voice_layer_uses_the_assembled_track_and_its_gain(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'assets/sfx').mkdir(parents=True);(root/'assets/voice').mkdir(parents=True)
            def tone(path,frequency,duration,channels=1):
                subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=%d:duration=%s:sample_rate=48000'%(frequency,duration),'-ac',str(channels),str(path)],check=True)
            tone(root/'assets/music.wav',300,2,2)
            tone(root/'assets/voice/voiceover.wav',700,2)
            tone(root/'assets/voice/line-01.wav',700,1)
            shutil.copy(ROOT/'assets/audio/sfx/click.wav',root/'assets/sfx/click.wav')
            plan={'demo':True,'style':'repo','duration':2,'fps':30,'width':1920,'height':1080,'audioRequired':True,'sfxRequired':True,'voiceoverRequired':True,
                  'motion':{'uiEffects':True,'cameraMove':True},
                  'shots':[{'id':'intro','start':0,'end':2,'type':'title','headline':'旁白进混音','claim':False,'source':[],
                            'description':'旁白进混音。','descriptionAt':0,'plainExplanation':'旁白进混音。',
                            'actions':[{'id':'line-appear','at':0.8,'action':'重点行出现','soundRequired':True}]}],
                  'audio':{'ducking':{'enabled':True},'music':{'file':'assets/music.wav','gain':0.6},
                           'voiceover':{'file':'assets/voice/voiceover.wav','gain':1.0,
                                        'lines':[{'shot':'intro','at':0.2,'duration':1.0,'text':'旁白进混音。','file':'assets/voice/line-01.wav'}]},
                           'cues':[{'at':0.8,'actionId':'line-appear','file':'assets/sfx/click.wav','gain':0.8,'role':'sfx','kind':'click'}]}}
            plan_path=root/'plan.json'
            def mix_with(gain):
                plan['audio']['voiceover']['gain']=gain
                plan_path.write_text(json.dumps(plan,ensure_ascii=False))
                subprocess.run([sys.executable,str(ROOT/'scripts/mix_audio.py'),str(plan_path)],capture_output=True,check=True)
                report=json.loads((root/'evidence/audio-mix.json').read_text())
                stem=root/('stem-%s.wav'%gain);shutil.copy(root/'assets/voice-stem.wav',stem)
                return report,stem
            loud,loud_stem=mix_with(1.0)
            (root/'assets/voice/line-01.wav').unlink()
            quiet,quiet_stem=mix_with(0.4)
            self.assertTrue(loud.get('voiceStem'),'a narrated mix keeps an isolated voice stem')
            self.assertEqual(loud['normalization']['requested']['integratedLufs'],-14)
            self.assertIn('voice',{window['kind'] for window in loud['ducking']['windows']})
            self.assertEqual(loud['voiceover']['file'],'assets/voice/voiceover.wav')
            self.assertIn('sha256',loud['voiceover'])
            self.assertTrue(any(line.get('sha256') for line in loud['voiceover']['lines']),'per-line evidence keeps its hash')
            self.assertFalse(any(line.get('sha256') for line in quiet['voiceover']['lines']),'missing per-line files remain optional evidence')
            # 1.0 versus 0.4 is about 8 dB, so the overall gain has to reach the mixed voice track.
            self.assertLess(mean_volume(quiet_stem),mean_volume(loud_stem)-5)


class Preflight(unittest.TestCase):
    def probe(self,project,launch_ok=True,extra=()):
        def fake_run(args,cwd=None,timeout=30):
            out=''
            if '--version' in args:out='v22.0.0' if 'node' in args[0] else '10.0.0'
            elif '-version' in args:out='ffmpeg 8'
            elif '-filters' in args:out='volume adelay amix loudnorm afade aresample asetnsamples'
            elif '-encoders' in args:out='libx264 aac'
            elif '-e' in args:
                js=args[args.index('-e')+1]
                if 'chromium.launch' in js:
                    if not launch_ok:return {'ok':False,'stdout':'','stderr':'Permission denied','output':'Permission denied'}
                else:
                    self.assertNotIn('executablePath()',js)
                    out=json.dumps({k:{'version':'1.0','path':'/unavailable/'+k} for k in ['playwright','esbuild','react','react-dom','gsap','three']})
            return {'ok':True,'stdout':out,'stderr':'','output':out}
        with patch.object(environment,'run',side_effect=fake_run),patch.object(environment.shutil,'which',side_effect=lambda n:'/bin/'+n),patch('sys.argv',['check_environment','--project',str(project),*extra]),contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as caught:environment.main()
        return caught.exception.code,json.loads(output.getvalue())
    def test_headless_only_and_cache_revalidation(self):
        with tempfile.TemporaryDirectory() as d:
            code,result=self.probe(Path(d));self.assertEqual(code,0);self.assertTrue(result['ready']);self.assertTrue(result['browser']['launched'])
            code,result=self.probe(Path(d));self.assertTrue(result['cached'])
            code,result=self.probe(Path(d),False);self.assertEqual(code,1);self.assertFalse(result['cached']);self.assertIn('browser-launch',result['missing'])
    def test_narration_decision_gates_the_key_and_nothing_else(self):
        # The key depends on the step-1 answer, not on the machine, so it is reported
        # separately and must never be read as a broken toolchain.
        with tempfile.TemporaryDirectory() as d:
            project=Path(d)
            with patch.dict(os.environ,{},clear=False):
                os.environ.pop('EASYROUTER_API_KEY',None)
                code,result=self.probe(project)
                self.assertEqual(code,0);self.assertEqual(result['prereqs'],[])
                self.assertEqual(result['voiceover'],{'requested':False,'keyResolved':False,'keySource':None})
                code,result=self.probe(project,extra=['--voiceover','no'])
                self.assertEqual(result['prereqs'],[]);self.assertFalse(result['warnings'])
                code,result=self.probe(project,extra=['--voiceover','undecided'])
                self.assertEqual(code,0);self.assertEqual(result['prereqs'],[])
                self.assertTrue(any('undecided' in w for w in result['warnings']))
                code,result=self.probe(project,extra=['--voiceover','yes'])
                self.assertEqual(code,1);self.assertEqual(result['prereqs'],['easyrouter-api-key']);self.assertFalse(result['ready'])
                self.assertNotIn('easyrouter-api-key',result['missing'])
                self.assertTrue(result['browser']['launched'])
                self.assertIn('Ask the user',result['next'])
    def test_narration_key_resolution_never_echoes_the_secret(self):
        with tempfile.TemporaryDirectory() as d:
            project=Path(d);secret='sk-must-not-appear-anywhere'
            (project/'.env').write_text('# comment\nOTHER=1\nEASYROUTER_API_KEY="%s"\n'%secret)
            with patch.dict(os.environ,{},clear=False):
                os.environ.pop('EASYROUTER_API_KEY',None)
                code,result=self.probe(project,extra=['--voiceover','yes'])
                self.assertEqual(code,0)
                self.assertEqual(result['voiceover'],{'requested':True,'keyResolved':True,'keySource':'.env'})
                self.assertNotIn(secret,json.dumps(result,ensure_ascii=False))
                self.assertNotIn(secret,(project/'evidence/environment.json').read_text())
                with patch.dict(os.environ,{'EASYROUTER_API_KEY':'  '+secret+'  '}):
                    code,result=self.probe(project,extra=['--voiceover','yes'])
                    self.assertEqual(result['voiceover']['keySource'],'environment')
                    self.assertNotIn(secret,json.dumps(result,ensure_ascii=False))


class Starter(unittest.TestCase):
    def test_default_repo_and_unedited_demo_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d)/'repo';repo.mkdir();project=Path(d)/'video'
            subprocess.run([sys.executable,str(ROOT/'scripts/init_project.py'),'--output',str(project),'--style','default','--repo',str(repo)],capture_output=True,check=True)
            plan=json.loads((project/'plan.json').read_text())
            self.assertEqual(plan['repo'],str(repo.resolve()))
            self.assertIn(str(repo.resolve()),(project/'BRIEF.md').read_text())
            plan['demo']=False
            self.assertTrue(any('at least one' in e for e in delivery.check(plan,project_dir=project)['errors']))
    def test_init_writes_direction_questions_not_answers(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d)/'repo';repo.mkdir();project=Path(d)/'video'
            subprocess.run([sys.executable,str(ROOT/'scripts/init_project.py'),'--output',str(project),'--style','repo','--repo',str(repo)],capture_output=True,check=True)
            text=(project/'DIRECTION.md').read_text()
            for heading in ['参考拆解','产品气质','三个方向','选择与理由','画面规范','镜头表']:self.assertIn(heading,text)
            self.assertIn('不要照抄',text)
            self.assertTrue((project/'src/engine.js').is_file())
    def test_sample_views_cover_plan_shots(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d)/'repo';repo.mkdir();project=Path(d)/'video'
            subprocess.run([sys.executable,str(ROOT/'scripts/init_project.py'),'--output',str(project),'--style','repo','--repo',str(repo)],capture_output=True,check=True)
            ids=[s['id'] for s in json.loads((project/'plan.json').read_text())['shots']]
            index=(project/'src/shots/index.js').read_text()
            for i in ids:self.assertIn(i+':',index)
class FirstFrame(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg needed')
    def test_blank_opening_fails_production(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            blank=root/'blank.mp4';busy=root/'busy.mp4'
            for src,out in [('color=c=0xfafaf9:s=640x360:r=30:d=1',blank),('testsrc2=s=640x360:r=30:d=1',busy)]:
                subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',src,'-pix_fmt','yuv420p',str(out)],check=True)
            self.assertTrue(all(r<0.004 for r in delivery.first_frame_metrics(blank)['inkRatio']))
            self.assertTrue(all(r>0.004 for r in delivery.first_frame_metrics(busy)['inkRatio']))
class Mix(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg needed')
    def test_outputs_are_capped_to_film_duration(self):
        import math,struct,wave
        mixer=module('mix_audio')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'assets/sfx').mkdir(parents=True)
            def tone(path,seconds,freq,channels=2):
                rate=48000;frames=[]
                for i in range(int(rate*seconds)):
                    v=int(0.3*32767*math.sin(2*math.pi*freq*i/rate));frames+= [v]*channels
                with wave.open(str(path),'wb') as w:w.setnchannels(channels);w.setsampwidth(2);w.setframerate(rate);w.writeframes(struct.pack('<%dh'%len(frames),*frames))
            tone(root/'assets/music.wav',3.2,220);tone(root/'assets/sfx/a.wav',0.4,880);tone(root/'assets/sfx/b.wav',1.5,660,1)
            actions=[{'id':f'k{i}','at':0.2+i*0.3,'action':'key','soundRequired':True} for i in range(8)]
            cues=[{'at':a['at'],'actionId':a['id'],'file':'assets/sfx/'+('a' if i%2 else 'b')+'.wav','gain':0.8,'role':'sfx','kind':'click'} for i,a in enumerate(actions)]
            plan={'duration':3,'fps':30,'shots':[{'id':'s','start':0,'end':3,'actions':actions}],'audio':{'music':{'file':'assets/music.wav','gain':0.6},'cues':cues,'ducking':{'enabled':True}}}
            (root/'plan.json').write_text(json.dumps(plan))
            with contextlib.redirect_stdout(io.StringIO()):mixer.mix(root/'plan.json')
            for name in ['sfx-stem.wav','music-ducked.wav','master.wav']:
                out=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(root/'assets'/name)],capture_output=True,text=True).stdout
                self.assertAlmostEqual(float(out),3.0,delta=0.05,msg=name)
class Landmarks(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg needed')
    def test_onset_and_peak(self):
        import math,struct,wave
        landmarks=module('sfx_landmarks').landmarks
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'hit.wav';rate=48000;data=[]
            for i in range(rate):
                t=i/rate;amp=0 if t<0.25 else (0.4 if t<0.5 else 0.9*math.exp(-(t-0.5)*8))
                data.append(int(amp*32767*math.sin(2*math.pi*440*t)))
            with wave.open(str(f),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(struct.pack('<%dh'%len(data),*data))
            r=landmarks(f)
            self.assertAlmostEqual(r['onset'],0.25,delta=0.01)
            self.assertAlmostEqual(r['peak'],0.5,delta=0.01)
            self.assertAlmostEqual(r['peakDbfs'],-0.9,delta=0.3)

if __name__=='__main__':unittest.main()
