"""Accept the single visible CUDA identity, never equate Slurm and device indices."""
import re

def valid_mask(mask):
    return mask=='0' or bool(isinstance(mask,str) and re.fullmatch(r'GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',mask))

def mask_matches(mask,selected):
    return valid_mask(mask) and valid_mask(selected) and selected!='0' and (mask=='0' or mask.lower()==selected.lower())

def patch_identity(source):
    from image_live_2plus4_20261011 import change
    source=change(source,"    if os.environ.get('CUDA_VISIBLE_DEVICES')!='0':raise RuntimeError('expected native single-device mask')",
        "    from image_cuda_contract_20261011 import valid_mask,mask_matches\n    if not valid_mask(os.environ.get('CUDA_VISIBLE_DEVICES')):raise RuntimeError('expected a single-device mask')")
    return change(source,"    selected_uuid='GPU-'+str(uuid.UUID(bytes=bytes(raw_uuid)))",
        "    selected_uuid='GPU-'+str(uuid.UUID(bytes=bytes(raw_uuid)))\n    if not mask_matches(os.environ.get('CUDA_VISIBLE_DEVICES'),selected_uuid):raise RuntimeError('CUDA mask does not match observed UUID')")

def patch_resolver(source):
    from image_live_2plus4_20261011 import change
    source=change(source,'import stat\n','import stat\nfrom image_cuda_contract_20261011 import mask_matches\n')
    return change(source,"record.get('cuda_visible_devices')!='0'","not mask_matches(record.get('cuda_visible_devices'),record.get('selected_uuid'))")
