# 小Jo英语默写

一个单文件英语默写网页。打开 `index.html` 或 `jo-dictation.html` 即可使用。

功能：

- 英文单词和短语听写
- 浏览器 text-to-speech 发音
- 中文提示、首词提示、对错判断
- 内置 `8B Unit 1` 到 `8B Unit 6`，顺序按 docx 文档排列
- 练习范围可细分到 `A`、`B`、`C`、`D` 小节，例如只练 `8B Unit 4 Fashion · B`
- 支持手动添加和批量导入词组

URL 参数：

- `?unit=8B%20Unit%204%20Fashion&section=A&order=inOrder`：直接打开 Unit 4 A，按文档顺序
- `?unit=8B%20Unit%204%20Fashion&section=C&order=shuffle`：直接打开 Unit 4 C，打乱顺序
- `?unit=8B%20Unit%204%20Fashion&order=wrongOnly`：直接打开 Unit 4 全单元错题

`order` 可选：`inOrder`、`shuffle`、`wrongOnly`。

更新内置词库：

```bash
python3 tools/import_docx_vocab.py --source /path/to/jo-diction --html index.html
```
