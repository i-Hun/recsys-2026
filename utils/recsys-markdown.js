import MarkdownIt from "markdown-it";
// Only this renderer may feed v-html. Raw HTML and images are intentionally disabled.
const markdown = new MarkdownIt({
  html: false,
  linkify: false,
  typographer: false,
});
markdown.renderer.rules.image = () => "";
export const renderReview = (text) => markdown.render(text);
