---
name: read-docx-arch
description: 当用户需要读取、分析或理解 .docx 格式的文档（尤其是包含架构图、时序图的架构设计文档）时触发。提取文字内容和所有嵌入图片供 AI 分析。
---

# 读取 docx 文档的文字与图片

## 描述
本技能用于直接读取 .docx 文件中的文字内容（保留标题层级）和嵌入图片（如架构图、时序图、流程图等），无需转换为 Markdown。

## 使用场景
- 用户要求读取、分析或理解某个 .docx 文档
- 文档中包含架构图、时序图、流程图等需要视觉分析的图片
- 用户提到"架构设计文档"、"技术方案"、"设计稿"等

## 不使用的场景
- 文件不是 .docx 格式
- 用户只是询问文件位置，不需要读取内容

## 输入
- file_path: string  # docx 文件的绝对路径或相对路径

## 输出
- 文档的文字内容（标题层级保留）
- 提取的图片文件路径列表
- 文档的结构化分析

## 指令

### Step 1: 运行提取脚本
执行位于当前 Skill 目录下的提取脚本：
```bash
python "${workspaceFolder}/.trae/skills/read-docx-arch/resources/read_docx.py" "{file_path}"
```
脚本依赖 `python-docx`，如果未安装，先执行：
```bash
pip install python-docx
```

### Step 2: 解析脚本输出
脚本输出 JSON 格式结果，包含以下字段：
- `success`: 是否成功
- `error`: 错误信息（失败时）
- `title`: 文档标题（文件名）
- `paragraphs`: 所有段落文字数组（标题带 `#` 前缀）
- `tables`: 所有表格内容数组
- `image_count`: 提取的图片数量
- `images_dir`: 图片保存目录
- `image_files`: 图片文件绝对路径数组
- `text_preview`: 前50段文字预览

### Step 3: 向用户展示文字内容
将 `paragraphs` 和 `tables` 的内容整理后展示给用户。保留标题层级，方便用户理解文档结构。

### Step 4: 引用图片到对话
如果 `image_count > 0`：
1. 告知用户提取到的图片数量和保存位置
2. 指导用户通过 `#File` 或 `#Folder` 将图片添加到对话上下文，以便进行视觉分析
3. 图片路径在 `image_files` 数组中

### Step 5: 综合分析
结合文字内容和图片，对文档进行结构化分析，例如：
- 文档的整体结构和章节划分
- 架构设计的核心模块和交互关系
- 时序图描述的关键流程
- 技术方案的关键决策点

## 失败处理
- `python-docx` 未安装：提示用户运行 `pip install python-docx`
- 文件不存在：返回明确错误
- 提取失败：返回脚本输出的 `error` 信息
- 无图片：正常返回文字内容，提示用户文档中没有嵌入图片