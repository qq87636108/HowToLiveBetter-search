// 高性价比人生 2.0 · 广告配置示例（开源发布用）
// 用法：复制为 site/core/ads-config.js 后填入真实值（真实文件已在 .gitignore 中，不进公开仓库）
const ADS_CONFIG = {
  enableAds: false,                      // 总开关：AdSense 过审并开始投放后再置 true
  adClient: "ca-pub-XXXXXXXXXXXXXXXX",   // 待填：AdSense 发布者 ID
  adSlotHome: "",                        // 待填：首页广告单元 ID
  adSlotDetail: "",                      // 待填：详情页广告单元 ID
  adFormat: "auto",
  debug: false                           // 开发/测试机阶段=true 显示占位框；生产必须 false
};
if (typeof window !== 'undefined') window.ADS_CONFIG = ADS_CONFIG;
