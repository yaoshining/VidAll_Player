import playerSessionTest from './PlayerSession.test';
import trackPresentationTest from './TrackPresentation.test';
import webDavServiceTest from './webdav/WebDavService.test';

export default function testsuite(): void {
  playerSessionTest();
  trackPresentationTest();
  webDavServiceTest();
}
