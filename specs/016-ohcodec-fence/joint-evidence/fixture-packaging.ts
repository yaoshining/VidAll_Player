// 仅用于隔离诊断夹具：保留设备日志，不用于生产交付。
import { hapTasks } from '@ohos/hvigor-ohos-plugin';
import * as fs from 'fs';
import * as path from 'path';
export default {
 system: hapTasks,
 plugins: [{pluginId: 'fixture-observable-release', apply(node) {
  node.afterNodeEvaluate(() => {
   node.getTaskByName('default@PackageHap')?.beforeRun(() => {
    for (const phase of ['merge_profile', 'process_profile', 'res', 'package']) {
     const file=path.join(node.getNodePath(), 'build/default/intermediates', phase, 'default/module.json');
     if (fs.existsSync(file)) { const data=JSON.parse(fs.readFileSync(file,'utf8')); data.app.debug=true; fs.writeFileSync(file,JSON.stringify(data)); }
    }
   });
  });
 }}]
};
