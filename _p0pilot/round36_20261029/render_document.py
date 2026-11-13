"""Use packaged DOCX renderer with installed Word PDF adapter."""
import os,json,importlib.util
from pathlib import Path
from pypdf import PdfReader
H=Path(__file__).resolve().parent
os.environ['PATH']='C:/Users/91344/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin'+os.pathsep+os.environ.get('PATH','')
spec=importlib.util.spec_from_file_location('packaged_renderer','C:/Users/91344/.codex/plugins/cache/openai-primary-runtime/documents/26.1025.11240/skills/documents/render_docx.py')
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
R.convert_to_pdf=lambda *a,**k:(str(H/'版式核验.pdf'),'Read-only Microsoft Word PDF adapter; no external solver or training')
pages=R.rasterize(str(H/'完成工作_图表补充候选.docx'),str(H/'页面预览'),105,False,False)
pdf=PdfReader(H/'版式核验.pdf')
report=dict(pages=len(pages),images=pages,text_chars=[len(p.extract_text()) for p in pdf.pages],blank_pages=[i+1 for i,p in enumerate(pdf.pages) if len(p.extract_text().strip())<30])
(H/'版式检查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
