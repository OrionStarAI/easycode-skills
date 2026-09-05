# HTML 演示文稿制作与录制指南

用 HTML 制作 PPT（替代 pptxgenjs），动机：CSS/JS 动态效果在**屏幕录制**时才能被真实捕捉（静帧 concat 会丢失动画）。同时保留可交互调试能力。

## deck.html 结构约定（record_deck.py 依赖，勿偏离）

```html
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html,body{margin:0;background:#101014;font-family:"PingFang SC",sans-serif}
  .slide{width:1280px;height:720px;position:absolute;inset:0;margin:auto;
         display:none;overflow:hidden}
  .slide.active{display:flex}
  .anim{opacity:0;transform:translateY(24px);transition:all .6s ease .15s}
  .slide.active .anim{opacity:1;transform:none}
  /* 依次延迟：.anim:nth-child(2){transition-delay:.3s} … */
</style></head>
<body>
  <section class="slide">…</section>   <!-- 每页一个 section，顺序即页序 -->
  …
<script>
  let cur = 0;
  const slides = document.querySelectorAll('.slide');
  function goToPage(n){                    // 录制控制协议：必须暴露此函数
    cur = Math.max(0, Math.min(slides.length-1, n));
    slides.forEach((s,i)=>s.classList.toggle('active', i===cur));
  }
  document.addEventListener('keydown', e=>{   // 键盘调试：←→翻页
    if(e.key==='ArrowRight') goToPage(cur+1);
    if(e.key==='ArrowLeft')  goToPage(cur-1);
  });
  goToPage(0);
</script>
</body></html>
```

## 设计规范（沿用大会演讲审美）

- 三角色配色：BACKGROUND（60–70%）→ PRIMARY（结构/图表）→ ACCENT（唯一强调色，5–10%），从主题派生
- 深色封面/结尾 + 浅色内容页三明治；母题统一（卡片圆角、大数字、同款装饰）
- 每页一个视觉焦点：大数字/图表/示意图/单一金句；**无纯文字页**
- 图表用 SVG/HTML 原生绘制（录制成像锐利）；禁外链图片（录制时网络抖动会白屏）
- 字号下限：正文 ≥20px（1280 画布）；标题 ≥44px
- 动画克制：进场 fade/translate 0.4–0.8s、每元素错开 0.15–0.3s；**不做循环动画**（停留态不定，录制时长难对齐；若必须循环，RecordTimeLine 以循环整周期取停）
- 中文排版：整页留 8% 呼吸位，行宽 ≤38 字符

## 与录制的时间契约

- 每页停留时长 = 该页所有分镜段视频时长之和（`record_deck.py --timeline` 自动从 manifest 聚合）
- 页切换即刻调用 `goToPage(n)`；动画进场时间（<1.5s）自然被页首覆盖
- **录制前自测**：浏览器打开 deck.html，←→ 键翻页确认动画与排版；再跑录制

## 常见坑

- playwright 录制窗口须 ≥1280×720（`viewport:{width:1280,height:720}`），DPR=1，否则模糊
- 字体用系统 PingFang SC（勿 @font-face 外链，录制时加载时序不稳）
- `display:none→flex` 触发 transition 需元素已在 DOM；用 `.active` 类切换而非 innerHTML 重写
- 录制产物是 webm → `ffmpeg -i in.webm -c:v libx264 -crf 18 -pix_fmt yuv420p -r 30 out.mp4` 转换并统一 30fps
