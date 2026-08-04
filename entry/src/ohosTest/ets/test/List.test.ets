import playerSessionTest from './PlayerSession.test';
import streamingSessionTest from './StreamingSession.test';
import streamingInternalsTest from './StreamingInternals.test';
import mediaKindDetectionTest from './player/MediaKindDetection.test';
import demoLifecycleTest from './player/DemoLifecycle.test';
import trackPresentationTest from './TrackPresentation.test';
import videoLetterboxTest from './videoLetterbox.test';
import webDavServiceTest from './webdav/WebDavService.test';
import sessionInfrastructureTest from './SessionInfrastructure.test';

export default function testsuite(): void {
  playerSessionTest();
  streamingSessionTest();
  streamingInternalsTest();
  mediaKindDetectionTest();
  demoLifecycleTest();
  trackPresentationTest();
  videoLetterboxTest();
  webDavServiceTest();
  sessionInfrastructureTest();
}
