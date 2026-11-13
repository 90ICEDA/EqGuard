"""Rasterize the Word-exported PDF with the packaged DOCX render helper.

The packaged LibreOffice executable is unavailable on this Windows host.
The manuscript was exported read-only through the installed Microsoft Word.
This adapter substitutes that PDF only; it does not edit the packaged helper.
"""
import importlib.util
import json
import os
from pathlib import Path
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent
PDF=HERE/'构建与核验/论文版式核验.pdf'
DOCX=HERE/'面向等价网表的图神经网络硬件木马检测模型研究.docx'
HELPER=Path('C:/Users/91344/.codex/plugins/cache/openai-primary-runtime/documents/26.1025.11240/skills/documents/render_docx.py')
POPPLER='C:/Users/91344/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin'
os.environ['PATH']=POPPLER+os.pathsep+os.environ.get('PATH','')
assert PDF.exists() and PDF.stat().st_mtime>=DOCX.stat().st_mtime
spec=importlib.util.spec_from_file_location('packaged_docx_renderer',HELPER)
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
renderer.convert_to_pdf=lambda *args,**kwargs:(str(PDF),'Read-only Word export; LibreOffice unavailable')
output=HERE/'构建与核验/版式预览_v3'
pages=renderer.rasterize(str(DOCX),str(output),110,False,False)
pdf=PdfReader(PDF)
report=dict(renderer='Packaged render_docx.rasterize with native Word PDF adapter',
            pages=len(pages),page_text_chars=[len(p.extract_text()) for p in pdf.pages],
            blank_pages=[i+1 for i,p in enumerate(pdf.pages) if len(p.extract_text().strip())<40],
            images=[str(Path(p).relative_to(HERE)) for p in pages])
(HERE/'构建与核验/版式检查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
