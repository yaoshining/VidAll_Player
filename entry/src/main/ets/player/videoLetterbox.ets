// 视频letterbox（按比例居中）尺寸计算的纯函数实现。
// 之所以从 Index 页面中抽出为独立、无 ArkUI 依赖的纯函数，
// 是为了能在不依赖 UI 渲染的前提下进行单元测试覆盖。
//
// 背景：曾使用 ArkUI 的 `.aspectRatio()` + `.constraintSize()` 在 Stack 场景下
// 自动计算内部视频框尺寸，但实测尺寸解析不稳定（观察到失控放大到远超外框，
// 例如 3819x2148），导致原生缓冲区与 XComponent 实际渲染尺寸不匹配、画面无法
// 正常显示（全黑）。因此改为由业务代码显式计算确定的宽高。

export interface VideoBoxSize {
  width: number;
  height: number;
}

/**
 * 根据外框（画框）尺寸与目标视频宽高比，计算等比缩放后、居中显示的内框尺寸（letterbox）。
 *
 * @param outerWidth 外框宽度（vp），必须 > 0
 * @param outerHeight 外框高度（vp），必须 > 0
 * @param aspectRatio 视频宽高比（width / height），必须 > 0
 * @returns 内框宽高（vp，向下取整，最小为 1），若入参非法则返回 undefined
 */
export function computeLetterboxSize(
  outerWidth: number,
  outerHeight: number,
  aspectRatio: number
): VideoBoxSize | undefined {
  if (!(outerWidth > 0) || !(outerHeight > 0) || !(aspectRatio > 0)) {
    return undefined;
  }

  const outerRatio = outerWidth / outerHeight;
  let boxWidth: number;
  let boxHeight: number;
  if (outerRatio > aspectRatio) {
    // 外框更「宽」：以高度为基准，两侧留黑边。
    boxHeight = outerHeight;
    boxWidth = boxHeight * aspectRatio;
  } else {
    // 外框更「窄」（或宽高比相等）：以宽度为基准，上下留黑边。
    boxWidth = outerWidth;
    boxHeight = boxWidth / aspectRatio;
  }

  return {
    width: Math.max(1, Math.floor(boxWidth)),
    height: Math.max(1, Math.floor(boxHeight)),
  };
}
