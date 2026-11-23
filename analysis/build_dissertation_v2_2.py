"""Build bilingual v2.2 using the established document formatting."""
from pathlib import Path
import runpy
R=Path(__file__).resolve().parents[1]
module=runpy.run_path(str(R/'analysis/build_dissertation_v2.py'))
build=module['build'];build.__globals__['ROOT']=R/'manuscript/v2_2'
for language in ('en','zh'):build(language)
