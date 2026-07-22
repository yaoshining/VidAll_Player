import playerSessionTest from './PlayerSession.test';
import webDavServiceTest from './webdav/WebDavService.test';

export default function testsuite(): void {
  playerSessionTest();
  webDavServiceTest();
}
