"""Two deterministic public-training-only fixtures; no official test reads."""
import csv
from pathlib import Path
import shutil
import zipfile
from lifecycle_pilot import sha

def cactus_split(rows,query_count=64):
 rows=sorted(rows,key=lambda r:r['id'])
 if len(rows)<=query_count or len({r['id'] for r in rows})!=len(rows):raise ValueError('cactus identity/count')
 if any(Path(r['id']).name!=r['id'] or not r['id'].endswith('.jpg') for r in rows):raise ValueError('image basename')
 query=rows[:query_count];train=rows[query_count:]
 if {r['has_cactus'] for r in train}!={'0','1'}:raise ValueError('binary training classes')
 return train,[r['id'] for r in query]

def numeric_split(names,training_count=31,query_count=2):
 if any(Path(n).name!=n or not n.endswith('.png') or not Path(n).stem.isdigit() for n in names):raise ValueError('numeric PNG basename')
 names=sorted(names,key=lambda n:int(Path(n).stem))
 if len(names)<training_count+query_count or len({int(Path(n).stem) for n in names})!=len(names):raise ValueError('denoising identity/count')
 return names[:training_count],names[training_count:training_count+query_count]

def make_cactus(source,out):
 from PIL import Image
 out.mkdir();(out/'train').mkdir();(out/'test').mkdir()
 # Private per-episode cache is writable; source images/labels stay read-only.
 (out/'workspace_cache').symlink_to('/workspace/input_cache',target_is_directory=True)
 with (source/'train.csv').open(newline='') as f:
  reader=csv.DictReader(f);fields=reader.fieldnames;train,query=cactus_split(list(reader))
 if fields!=['id','has_cactus']:raise ValueError('cactus columns')
 train_ids={r['id'] for r in train};required=train_ids|set(query)
 source_pins=[dict(path=str(source/name),sha256=sha(source/name)) for name in ('train.csv','train.zip')]
 with zipfile.ZipFile(source/'train.zip') as z:
  members={}
  for info in z.infolist():
   if info.is_dir():continue
   p=Path(info.filename)
   if p.name not in required:continue
   if info.filename not in (p.name,'train/'+p.name) or p.name in members:raise ValueError('ambiguous archive path')
   if info.file_size>2*1024**2:raise ValueError('unexpected image size')
   members[p.name]=info
  if set(members)!=required:raise ValueError('missing train image')
  for name,info in members.items():
   dst=out/('train' if name in train_ids else 'test')/name
   with dst.open('xb') as f:f.write(z.read(info))
   with Image.open(dst) as im:
    if im.size!=(32,32):raise ValueError('cactus image shape')
    im.verify()
 with (out/'train.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(train)
 with (out/'test.csv').open('x',newline='') as f:
  w=csv.writer(f);w.writerow(['id']);w.writerows([[n] for n in query])
 return dict(training_images=len(train),query_images=len(query),selection='lexicographic public IDs: first 64 query, all remaining train',
             original_source_subset_fraction=.2,query_disjoint=True,private_cache='/workspace/input_cache',source_pins=source_pins)

def make_denoising(source,out):
 from PIL import Image
 out.mkdir();[(out/n).mkdir() for n in ('train','train_cleaned','test')]
 train,query=numeric_split([p.name for p in (source/'train').iterdir() if p.is_file() and p.suffix=='.png'])
 source_pins=[];dimensions={}
 for name in train+query:
  noisy=source/'train'/name
  with Image.open(noisy) as im:dimensions[name]=im.size;im.verify()
  source_pins.append(dict(path=str(noisy),sha256=sha(noisy)))
  shutil.copyfile(noisy,out/('train' if name in train else 'test')/name)
  if name in train:
   clean=source/'train_cleaned'/name
   with Image.open(clean) as im:
    if im.size!=dimensions[name]:raise ValueError('paired dimensions')
    im.verify()
   source_pins.append(dict(path=str(clean),sha256=sha(clean)))
   shutil.copyfile(clean,out/'train_cleaned'/name)
 with (out/'test.csv').open('x',newline='') as f:
  w=csv.writer(f);w.writerow(['id'])
  for name in query:
   width,height=dimensions[name];stem=int(Path(name).stem)
   for row in range(1,height+1):
    w.writerows([[f'{stem}_{row}_{col}'] for col in range(1,width+1)])
 return dict(public_training_pairs=31,source_internal_train_images=16,source_internal_validation_images=15,query_images=2,
             query_pixels=sum(dimensions[n][0]*dimensions[n][1] for n in query),query_disjoint=True,
             selection='numeric public train stems: first 31 paired input, next 2 noisy-only query; never mount query clean images',source_pins=source_pins)

def files_manifest(root):
 return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
