import publicImportTest from './PublicImport.test';
import xcomponentLifecycleTest from './XComponentLifecycle.test';
import playerLifecycleTest from './PlayerLifecycle.test';

export default function testsuite(): void {
  publicImportTest();
  xcomponentLifecycleTest();
  playerLifecycleTest();
}
