"""Packaged rasterizer using the existing native Word read-only PDF adapter."""
import importlib.util,json,os
from pathlib import Path
from pypdf import PdfReader
H=Path(__file__).resolve().parent;B=H/'构建与核验'
PDF=B/'版式核验.pdf';DOCX=H/'面向等价网表的GNN木马检测研究阶段报告.docx'
HELPER=Path('C:/Users/91344/.codex/plugins/cache/openai-primary-runtime/documents/26.1025.11240/skills/documents/render_docx.py')
os.environ['PATH']='C:/Users/91344/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin'+os.pathsep+os.environ.get('PATH','')
assert PDF.stat().st_mtime>=DOCX.stat().st_mtime
spec=importlib.util.spec_from_file_location('packaged_docx_renderer',HELPER);renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
renderer.convert_to_pdf=lambda *args,**kwargs:(str(PDF),'Read-only native Word export; packaged LibreOffice unavailable on this host')
pages=renderer.rasterize(str(DOCX),str(B/'页面预览'),140,False,False)
pdf=PdfReader(PDF);report=dict(pages=len(pages),page_text_chars=[len(p.extract_text()) for p in pdf.pages],blank_pages=[i+1 for i,p in enumerate(pdf.pages) if len(p.extract_text().strip())<40],images=pages)
(B/'版式检查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
