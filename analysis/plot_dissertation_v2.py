"""Descriptive figures from frozen, already-scored results. No statistical tests.
Run with matplotlib installed. PNG 300dpi, editable SVG and vector PDF outputs.
"""
from pathlib import Path
import csv,json,hashlib
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'artifacts/dissertation_data/20261020T032924986612Z'
OUT=ROOT/'manuscript/v2/figures'
CATEGORICAL = ["#2166AC", "#B2182B", "#1B7837", "#F1A340", "#762A83", "#666666"]
CATEGORICAL_EXTENDED = [
    "#2166AC", "#B2182B", "#1B7837", "#F1A340", "#762A83", "#666666",
    "#4393C3", "#D6604D", "#5AAE61", "#B35806", "#9970AB", "#999999",
]
DIVERGING   = ["#2166AC", "#F7F7F7", "#B2182B"]
SEQUENTIAL  = ["#F7FBFF", "#6BAED6", "#08306B"]
ACCENT_RED  = "#B2182B"
GREY        = "#999999"
BLACK       = "#222222"
font=Path('/System/Library/Fonts/Supplemental/Arial.ttf')
if font.exists():font_manager.fontManager.addfont(str(font))
mpl.rcParams.update({'font.family':'Arial','font.size':10,'axes.labelsize':10,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,
 'pdf.fonttype':42,'svg.fonttype':'none','savefig.dpi':300})
def save(fig,name):
 for suffix in ('png','svg','pdf'):fig.savefig(OUT/f'{name}.{suffix}',bbox_inches='tight',dpi=300)
 plt.close(fig)
rows=list(csv.DictReader((DATA/'per_run.csv').open()))
main=[r for r in rows if r['group']=='main']
conditions=['T1_uploaded_only','T2_uploaded_only','T3_uploaded_only','T4_uploaded_only','T5_uploaded_only','T5_web_only','T6_hybrid']
labels=['T1  NVIDIA annual','T2  NVIDIA synthesis','T3  AMD annual (brief)','T4  AMD synthesis','T5  Compare: uploads','T5  Compare: web','T6  Compare: hybrid']
fig,ax=plt.subplots(figsize=(7.0,4.1));fig.subplots_adjust(left=.32,right=.97,bottom=.2,top=.89)
points=[]
for i,condition in enumerate(conditions):
 group=[r for r in main if r['condition']==condition]
 assert len(group)==3
 for j,r in enumerate(group):
  limit=500 if condition=='T3_uploaded_only' else 1400
  ratio=int(r['body_word_count'])/limit
  passed=r['automatic_passed']=='True'
  ax.scatter(ratio,i+(j-1)*.16,s=42,marker='o' if passed else 'x',color=CATEGORICAL[0] if passed else ACCENT_RED,linewidths=1.5,zorder=3)
  points.append({'run_id':r['run_id'],'words':int(r['body_word_count']),'upper_limit':limit,'ratio':ratio,'automatic_passed':passed})
ax.axvline(1,color=BLACK,ls='--',lw=1)
ax.set(yticks=range(7),yticklabels=labels,xlim=(.55,1.85),ylim=(6.5,-.5),xlabel='Body words / requested upper word limit')
ax.set_xticks([.6,.8,1.,1.2,1.4,1.6,1.8]);ax.grid(axis='x',color='#E5E5E5',lw=.6);ax.set_axisbelow(True)
fig.legend(handles=[Line2D([],[],marker='o',ls='',color=CATEGORICAL[0],label='Automatic pass'),Line2D([],[],marker='x',ls='',color=ACCENT_RED,label='Overlength')],loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.61,1.00))
save(fig,'length_compliance')
pairs=json.loads((DATA/'customization_pairs.json').read_text())
fig,ax=plt.subplots(figsize=(7.0,3.7));fig.subplots_adjust(left=.30,right=.96,bottom=.19,top=.86)
for i,p in enumerate(pairs):
 a,b=p['base_words'],p['variant_words'];ax.plot([a,b],[i,i],color=GREY,lw=1.7,zorder=1)
 ax.scatter(a,i,s=64,marker='o',color=CATEGORICAL[0],zorder=3)
 ax.scatter(b,i,s=64,marker='D',color=CATEGORICAL[3],edgecolor='#8A5700',linewidth=.7,zorder=3)
 ax.annotate(str(a),(a,i),xytext=(0,12),textcoords='offset points',ha='center',fontsize=10)
 ax.annotate(str(b),(b,i),xytext=(0,-21),textcoords='offset points',ha='center',fontsize=10)
ax.set(yticks=[0,1,2],yticklabels=['Structure\nStandard → comparative','Style\nFormal → concise','Depth\nBrief → detailed'],xlabel='Body words',xlim=(0,2500),ylim=(2.6,-.6))
ax.grid(axis='x',color='#E5E5E5',lw=.6);ax.set_axisbelow(True)
fig.legend(handles=[Line2D([],[],marker='o',ls='',color=CATEGORICAL[0],label='Baseline'),Line2D([],[],marker='D',ls='',color=CATEGORICAL[3],label='Single-setting variant')],loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.62,1.0))
save(fig,'customization_pairs')
metadata={'batch':'20261020T032924986612Z','purpose':'descriptive presentation of frozen results','main_n':21,'per_condition_n':3,'customization_pairs':3,'statistical_tests':None,'error_bars':None,'uncertainty_note':'No independent population inference; single customization variants. No smoothed densities or inferential intervals.','inputs':{name:hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in ['per_run.csv','customization_pairs.json']},'length_points':points,'pairs':pairs,'matplotlib_version':mpl.__version__}
(OUT/'plot_data.json').write_text(json.dumps(metadata,indent=2))
print('Saved two data figures in PNG/SVG/PDF and their exact inputs.')
