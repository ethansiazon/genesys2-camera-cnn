"""Only campaign-local dependencies are added. Original environments are untouched."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'deps'));sys.path.insert(0,str(ROOT/'vendor/yolov5'))
os.environ['YOLOv5_AUTOINSTALL']='false'
os.environ['MPLBACKEND']='Agg'
os.environ['GIT_PYTHON_REFRESH']='quiet'
sys.stdout.reconfigure(encoding='utf-8')
