"""Actual PEFT/Transformers execution; optional heavyweight dependencies, local models only."""
from hashlib import sha256
import json
from pathlib import Path
import time
from ..application.service import ServiceError
from ..application.storage import Storage
from ..adapters.model import ModelExchange
from ..reporting.identity import digest


def dependencies():
    try:
        import torch
        from transformers import AutoModelForCausalLM,AutoTokenizer,Trainer,TrainingArguments
        from peft import LoraConfig,TaskType,get_peft_model,PeftModel
        return locals()
    except ImportError:raise ServiceError('training_dependencies_missing') from None


def model_manifest(root):
    path=Path(root)
    if not path.is_dir():raise ServiceError('local_model_missing')
    return {str(p.relative_to(path)):sha256(p.read_bytes()).hexdigest() for p in sorted(path.rglob('*')) if p.is_file()}


def train(settings,config_path,*,execute=False):
    if not execute:raise ServiceError('training_requires_explicit_execute')
    config=json.loads(Path(config_path).read_text(encoding='utf-8'))
    if config.get('license_confirmed') is not True:raise ServiceError('base_model_license_confirmation_required')
    base=Path(config['base_model_path']).resolve();output=Path(config['output_dir']).resolve()
    if not output.is_relative_to((settings.project_root/'var/training').resolve()) or output.exists():raise ServiceError('training_output_must_be_new_runtime_directory')
    lib=dependencies();torch=lib['torch'];torch.manual_seed(config.get('seed',42))
    tokenizer=lib['AutoTokenizer'].from_pretrained(str(base),local_files_only=True,trust_remote_code=False)
    model=lib['AutoModelForCausalLM'].from_pretrained(str(base),local_files_only=True,trust_remote_code=False)
    tokenizer.pad_token=tokenizer.pad_token or tokenizer.eos_token
    lora=lib['LoraConfig'](r=config.get('rank',16),lora_alpha=config.get('alpha',32),lora_dropout=.05,
        target_modules=config.get('target_modules',['q_proj','v_proj']),bias='none',task_type=lib['TaskType'].CAUSAL_LM)
    model=lib['get_peft_model'](model,lora)
    trainable=sum(p.numel() for p in model.parameters() if p.requires_grad);total=sum(p.numel() for p in model.parameters())
    if not 0<trainable<total:raise ServiceError('invalid_lora_trainable_parameter_count')
    class Samples(torch.utils.data.Dataset):
        def __init__(self,file):
            self.rows=[]
            for line in Path(file).read_text(encoding='utf-8').splitlines():
                row=json.loads(line);prompt=tokenizer.apply_chat_template([{'role':'user','content':row['instruction']+'\n'+json.dumps(row['ssm'],ensure_ascii=False)}],tokenize=False,add_generation_prompt=True)
                prefix=tokenizer(prompt,add_special_tokens=False)['input_ids'];answer=tokenizer(row['san']+tokenizer.eos_token,add_special_tokens=False)['input_ids']
                if len(prefix)+len(answer)>config.get('max_length',8192):raise ServiceError('training_sample_exceeds_frozen_context')
                self.rows.append({'input_ids':prefix+answer,'labels':[-100]*len(prefix)+answer,'attention_mask':[1]*(len(prefix)+len(answer))})
        def __len__(self):return len(self.rows)
        def __getitem__(self,index):return self.rows[index]
    train_data=Samples(config['train_file']);valid_data=Samples(config['validation_file'])
    if not len(train_data) or not len(valid_data):raise ServiceError('training_and_validation_samples_required')
    def collate(rows):
        size=max(len(row['input_ids']) for row in rows)
        return {key:torch.tensor([row[key]+[pad]*(size-len(row[key])) for row in rows])
            for key,pad in [('input_ids',tokenizer.pad_token_id),('labels',-100),('attention_mask',0)]}
    # Dataset builder's group check is repeated at execution to prevent swapping unchecked files.
    train_rows=[json.loads(s) for s in Path(config['train_file']).read_text(encoding='utf-8').splitlines()]
    valid_rows=[json.loads(s) for s in Path(config['validation_file']).read_text(encoding='utf-8').splitlines()]
    if ({r['group'] for r in train_rows}&{r['group'] for r in valid_rows} or
        {r['source_sha256'] for r in train_rows}&{r['source_sha256'] for r in valid_rows}):raise ServiceError('training_group_leakage')
    receipt={'config':config,'base_model_sha256':digest(model_manifest(base)),
        'train_sha256':sha256(Path(config['train_file']).read_bytes()).hexdigest(),
        'validation_sha256':sha256(Path(config['validation_file']).read_bytes()).hexdigest(),
        'trainable_parameters':trainable,'total_parameters':total,'framework_versions':{
            name:__import__(name).__version__ for name in ('torch','transformers','peft')},'started_at':time.time()}
    storage=Storage(output);storage.put('training-request.json',json.dumps(receipt,sort_keys=True,indent=2).encode())
    args=lib['TrainingArguments'](output_dir=str(output/'checkpoints'),num_train_epochs=config.get('epochs',3),
        per_device_train_batch_size=1,per_device_eval_batch_size=1,gradient_accumulation_steps=config.get('gradient_accumulation_steps',8),
        learning_rate=config.get('learning_rate',2e-4),logging_steps=1,save_strategy='epoch',eval_strategy='epoch',
        report_to='none',seed=config.get('seed',42),dataloader_pin_memory=False)
    trainer=lib['Trainer'](model=model,args=args,train_dataset=train_data,eval_dataset=valid_data,data_collator=collate)
    result=trainer.train();evaluation=trainer.evaluate();model.save_pretrained(output/'adapter');tokenizer.save_pretrained(output/'adapter')
    receipt.update(finished_at=time.time(),metrics=result.metrics,evaluation=evaluation,adapter_files=model_manifest(output/'adapter'))
    storage.put('training-result.json',json.dumps(receipt,sort_keys=True,indent=2).encode());return receipt


class LocalLoraModel:
    def __init__(self,profile):self.profile=profile
    def preflight(self):
        dependencies()
        for key in ('base_model_path','adapter_path'):
            if not self.profile['learning'][key] or not Path(self.profile['learning'][key]).is_dir():raise ServiceError('local_lora_model_missing')
    def exchange(self,messages):
        self.preflight();lib=dependencies();torch=lib['torch'];conf=self.profile
        base=conf['learning']['base_model_path'];adapter=conf['learning']['adapter_path']
        tokenizer=lib['AutoTokenizer'].from_pretrained(base,local_files_only=True,trust_remote_code=False)
        model=lib['AutoModelForCausalLM'].from_pretrained(base,local_files_only=True,trust_remote_code=False)
        model=lib['PeftModel'].from_pretrained(model,adapter,local_files_only=True);model.eval()
        if torch.cuda.is_available():model=model.to('cuda')
        inputs=tokenizer.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,return_tensors='pt').to(model.device)
        with torch.no_grad():output=model.generate(inputs,max_new_tokens=conf['model']['max_output_tokens'],do_sample=False,pad_token_id=tokenizer.eos_token_id)
        answer=output[0,inputs.shape[-1]:];stop=answer[-1].item()==tokenizer.eos_token_id
        result={'model':conf['model']['model'],'choices':[{'finish_reason':'stop' if stop else 'length','message':{'role':'assistant','content':tokenizer.decode(answer,skip_special_tokens=True)}}],
            'usage':{'prompt_tokens':inputs.shape[-1],'completion_tokens':len(answer),'total_tokens':inputs.shape[-1]+len(answer)}}
        return ModelExchange(200,json.dumps(result).encode())
