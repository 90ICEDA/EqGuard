import importlib.util,os,json
from pathlib import Path
from pypdf import PdfReader
H=Path(__file__).resolve().parent;Q=H/'构建与核验'
os.environ['PATH']='C:/Users/91344/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin'+os.pathsep+os.environ.get('PATH','')
spec=importlib.util.spec_from_file_location('renderer','C:/Users/91344/.codex/plugins/cache/openai-primary-runtime/documents/26.1025.11240/skills/documents/render_docx.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
r.convert_to_pdf=lambda *args,**kwargs:(str(Q/'版式核验.pdf'),'Native Word read-only PDF adapter')
pages=r.rasterize(str(H/'拟完成的研究工作_围绕三问展开.docx'),str(Q/'页面预览'),110,False,False)
p=PdfReader(Q/'版式核验.pdf')
report={'pages':len(pages),'images':pages,'text_chars':[len(x.extract_text()) for x in p.pages]}
(Q/'版式检查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
