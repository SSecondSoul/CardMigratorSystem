"""Optional local vision embedding, auxiliary only; no model download or pass override."""
from io import BytesIO
from pathlib import Path
from ..application.service import ServiceError
from ..reporting.identity import digest


def similarity(model_path,first,second):
    if not model_path:return {'status':'not_configured','similarity':None}
    try:
        import torch
        from PIL import Image
        from transformers import AutoProcessor,CLIPModel
    except ImportError:raise ServiceError('embedding_dependencies_missing') from None
    from ..training.lora import model_manifest
    fingerprint=digest(model_manifest(model_path))
    processor=AutoProcessor.from_pretrained(model_path,local_files_only=True,trust_remote_code=False)
    model=CLIPModel.from_pretrained(model_path,local_files_only=True).eval()
    inputs=processor(images=[Image.open(BytesIO(first)).convert('RGB'),Image.open(BytesIO(second)).convert('RGB')],return_tensors='pt')
    with torch.no_grad():features=model.get_image_features(**inputs);features=features/features.norm(dim=-1,keepdim=True)
    return {'status':'completed','similarity':float((features[0]*features[1]).sum()),'model_files_sha256':fingerprint,
            'preprocessing':'frozen_local_AutoProcessor','role':'auxiliary_not_a_pass_gate'}
