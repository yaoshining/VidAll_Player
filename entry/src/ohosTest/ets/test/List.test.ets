import playerSessionTest from './PlayerSession.test';
import streamingSessionTest from './StreamingSession.test';
import streamingInternalsTest from './StreamingInternals.test';
import mediaKindDetectionTest from './player/MediaKindDetection.test';
import trackPresentationTest from './TrackPresentation.test';
import webDavServiceTest from './webdav/WebDavService.test';

export default function testsuite(): void {
  playerSessionTest();
  streamingSessionTest();
  streamingInternalsTest();
  mediaKindDetectionTest();
  trackPresentationTest();
  webDavServiceTest();
}
