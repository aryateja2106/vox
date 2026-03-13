#!/usr/bin/env python3
"""Fine-tune Qwen3.5-0.8B-Base on NL-to-shell dataset using LoRA.

Prerequisites:
  pip install "vox-shell[finetune]"
  # or: pip install transformers peft datasets torch

Usage:
  python scripts/finetune/train.py \
    --dataset data/nl2shell.jsonl \
    --base-model Qwen/Qwen3.5-0.8B-Base \
    --output models/vox-nl2shell \
    --epochs 3 \
    --batch-size 4 \
    --lr 2e-4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def format_prompt(instruction: str, output: str = "") -> str:
    """Format instruction/output pair for training."""
    prompt = (
        "You are an expert shell programmer on macOS. "
        "Given a natural language request, output ONLY the corresponding shell command. "
        "No explanations, no markdown, no code fences, no comments.\n\n"
        f"### Request:\n{instruction}\n\n"
        f"### Command:\n{output}"
    )
    return prompt


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Qwen3.5-0.8B on NL-to-shell")
    parser.add_argument("--dataset", required=True, help="Path to JSONL dataset")
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-0.8B-Base", help="HF model ID")
    parser.add_argument("--output", default="models/vox-nl2shell", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=256)
    args = parser.parse_args()

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForSeq2Seq,
            Trainer,
            TrainingArguments,
        )
    except ImportError:
        print(
            "Fine-tuning dependencies not installed.\n"
            'Install with: pip install "vox-shell[finetune]" torch',
            file=sys.stderr,
        )
        sys.exit(1)

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}", file=sys.stderr)
        print("Run: python scripts/finetune/build_dataset.py first", file=sys.stderr)
        sys.exit(1)

    print(f"Loading dataset from {dataset_path}...")
    with open(dataset_path) as f:
        raw_data = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(raw_data)} examples")

    print(f"Loading tokenizer and model: {args.base_model}...")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    def tokenize_fn(example):
        full_text = format_prompt(example["instruction"], example["output"])
        tokens = tokenizer(
            full_text,
            truncation=True,
            max_length=args.max_length,
            padding="max_length",
        )
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    dataset = Dataset.from_list(raw_data)
    tokenized = dataset.map(tokenize_fn, remove_columns=dataset.column_names)

    output_dir = Path(args.output)
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=2,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_ratio=0.1,
        logging_steps=10,
        save_strategy="epoch",
        bf16=True,
        report_to="none",
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True),
    )

    print("Starting training...")
    trainer.train()

    print(f"Saving model to {output_dir}...")
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    print("Done! To use the fine-tuned model:")
    print(f"  vox --model {output_dir} --provider mlx")
    print("  # or convert to Ollama: ollama create vox-nl2shell -f Modelfile")


if __name__ == "__main__":
    main()
