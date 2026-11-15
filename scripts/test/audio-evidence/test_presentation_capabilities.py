import unittest,importlib.util
from pathlib import Path
s=importlib.util.spec_from_file_location('pc',Path(__file__).with_name('presentation_capabilities.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Test(unittest.TestCase):
 def report(self,extensions):return {'querySucceeded':True,'devices':[{'extensionQuerySucceeded':True,'extensions':extensions}],'eglReadOnly':{'querySucceeded':True,'extensions':'EGL_KHR_fence_sync','frameTimestampsFunction':True,'frameSupportedFunction':True}}
 def test_symbols_are_not_capability(self):
  r=m.summarize(self.report(['VK_KHR_swapchain']));self.assertEqual(r['vulkanStatus'],'unsupported');self.assertEqual(r['eglStatus'],'unsupported');self.assertFalse(r['actualPresentationMeasured'])
 def test_supported_is_still_not_measured(self):
  r=m.summarize(self.report(['VK_GOOGLE_display_timing']));self.assertEqual(r['vulkanStatus'],'candidate');self.assertFalse(r['actualPresentationMeasured'])
 def test_query_failure_is_unknown(self):
  r=self.report([]);r['devices'][0]['extensionQuerySucceeded']=False;r['eglReadOnly']['querySucceeded']=False
  a=m.summarize(r);self.assertEqual(a['vulkanStatus'],'unknown');self.assertEqual(a['eglStatus'],'unknown')
 def test_extension_exact_match(self):
  r=self.report(['VK_GOOGLE_display_timing_fake']);r['eglReadOnly']['extensions']='EGL_ANDROID_get_frame_timestamps_fake';a=m.summarize(r);self.assertEqual(a['vulkanStatus'],'unsupported');self.assertEqual(a['eglStatus'],'unsupported')
if __name__=='__main__':unittest.main()
