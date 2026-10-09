// 高性价比人生 2.0 广告配置（文件式管理；开源发布时以 example 代替，真实文件不进公开仓库）
const ADS_CONFIG = {
  enableAds: false,                      // 总开关：过审拿钱后再 true（分档挂站铁律）
  adClient: "ca-pub-XXXXXXXXXXXXXXXX",   // 待填：AdSense pub-id
  adSlotHome: "",                        // 待填：首页广告单元 ID
  adSlotDetail: "",                      // 待填：详情页广告单元 ID
  adFormat: "auto",
  debug: false                            // 测试机阶段=true 显示占位框；生产默认关
};
if (typeof window !== 'undefined') window.ADS_CONFIG = ADS_CONFIG;
