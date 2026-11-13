
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[3]))
from eqguard_paths import project_path as _eqguard_path
import os, json, importlib.util
from pathlib import Path
from pypdf import PdfReader
H=Path(__file__).resolve().parent
R=Path(_eqguard_path(''))
doc=R/'10.15/08_论文写作/中期答辩_20261105/中期答辩逐页详细讲解_对应34页成果重点修订版_20261106.docx'
os.environ['PATH']='C:/Users/91344/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin'+os.pathsep+os.environ.get('PATH','')
spec=importlib.util.spec_from_file_location('packaged_renderer','C:/Users/91344/.codex/plugins/cache/openai-primary-runtime/documents/26.1030.10813/skills/documents/render_docx.py')
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
renderer.convert_to_pdf=lambda *a,**k:(str(H/'word_preview.pdf'),'Native Microsoft Word PDF adapter because LibreOffice is not installed; read-only export')
images=renderer.rasterize(str(doc),str(H/'render'),105,False,False)
pdf=PdfReader(H/'word_preview.pdf')
texts=[p.extract_text() for p in pdf.pages]
report={'pages':len(pdf.pages),'images':list(images),'chars_per_page':[len(t) for t in texts],'blank_pages':[i+1 for i,t in enumerate(texts) if len(t.strip())<40]}
(H/'render_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
(H/'rendered_text.txt').write_text('\n\n'.join(texts),encoding='utf8')
print(json.dumps(report,ensure_ascii=True))
