#!/usr/bin/env python3
"""
Convert HuggingFace model to GGUF format using the gguf library.
"""

import os
import sys
import json
import argparse
from pathlib import Path

import torch
import gguf
from transformers import AutoTokenizer, AutoConfig


def get_tensor_names(model):
    """Get all tensor names from the model."""
    tensor_names = set()
    for key in model.keys():
        tensor_names.add(key)
    return tensor_names


def read_model(model_path: Path):
    """Read model weights from safetensors files."""
    from safetensors import safe_open
    
    model = {}
    # Check for sharded files
    if (model_path / "model.safetensors.index.json").exists():
        with open(model_path / "model.safetensors.index.json") as f:
            index = json.load(f)
            for filename in index["weight_map"].values():
                shard_path = model_path / filename
                with safe_open(shard_path, framework="pt") as f:
                    for key in f.keys():
                        model[key] = f.get_tensor(key)
    else:
        # Single file
        for filename in model_path.glob("model-*.safetensors"):
            with safe_open(filename, framework="pt") as f:
                for key in f.keys():
                    model[key] = f.get_tensor(key)
    
    return model


def convert_to_gguf(model_path: str, output_path: str, quant_type: str = "f16"):
    """Convert HuggingFace model to GGUF format."""
    
    model_path = Path(model_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading model from {model_path}...")
    
    # Read config
    with open(model_path / "config.json") as f:
        config = json.load(f)
    
    # Extract model config
    vocab_size = config.get("vocab_size", 151936)
    hidden_size = config.get("hidden_size", 2048)
    num_attention_heads = config.get("num_attention_heads", 16)
    num_key_value_heads = config.get("num_key_value_heads", num_attention_heads)
    intermediate_size = config.get("intermediate_size", 5504)
    num_hidden_layers = config.get("num_hidden_layers", 24)
    rms_norm_eps = config.get("rms_norm_eps", 1e-6)
    max_position_embeddings = config.get("max_position_embeddings", 32768)
    
    # Read tokenizer
    print("Loading tokenizer...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True, fix_mistral_regex=True)
    except:
        tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True)
    
    # Read model weights
    print("Loading model weights...")
    model = read_model(model_path)
    
    # Get tensor names
    tensor_names = get_tensor_names(model)
    print(f"Found {len(tensor_names)} tensors")
    
    # Determine quantization type
    if quant_type == "f16":
        file_type = 1  # F16
    elif quant_type == "q8_0":
        file_type = 8  # Q8_0
    else:
        file_type = 1  # default to f16
    
    # Create GGUF writer with temp file
    print(f"Writing GGUF to {output_path}...")
    
    writer = gguf.GGUFWriter(str(output_path), "qwen2", use_temp_file=True)
    
    # Add model parameters
    writer.add_block_count(num_hidden_layers)
    writer.add_context_length(max_position_embeddings)
    writer.add_embedding_length(hidden_size)
    writer.add_head_count(num_attention_heads)
    writer.add_head_count_kv(num_key_value_heads)
    writer.add_layer_norm_rms_eps(rms_norm_eps)
    writer.add_feed_forward_length(intermediate_size)
    writer.add_vocab_size(vocab_size)
    writer.add_rope_dimension_count(hidden_size // num_attention_heads)
    
    # Add metadata
    writer.add_name(model_path.name)
    writer.add_quantization_version(2)
    writer.add_file_type(file_type)
    
    # Add tokenizer
    bos_id = tokenizer.bos_token_id if tokenizer.bos_token_id is not None else 151643
    eos_id = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 151645
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else -1
    
    writer.add_tokenizer_model("qwen2")
    
    if bos_id != -1 and bos_id is not None:
        writer.add_bos_token_id(bos_id)
    if eos_id != -1 and eos_id is not None:
        writer.add_eos_token_id(eos_id)
    if pad_id != -1 and pad_id is not None:
        writer.add_pad_token_id(pad_id)
    
    # Add vocab
    print("Adding vocabulary...")
    vocab = tokenizer.get_vocab()
    token_list = sorted(vocab.items(), key=lambda x: x[1])
    tokens = [t[0] for t in token_list]
    scores = [-100.0] * len(tokens)  # dummy scores
    
    writer.add_token_list(tokens)
    writer.add_token_scores(scores)
    
    # Add model weights
    print("Adding model weights...")
    
    # Map tensor names to GGUF format
    tensor_map = {
        "model.embed_tokens.weight": "token_embd.weight",
        "model.norm.weight": "output_norm.weight",
    }
    
    # tie_word_embeddings=true: lm_head shares with embed_tokens
    # We'll just skip lm_head or create a copy
    
    # Add attention layers (including bias tensors)
    for i in range(num_hidden_layers):
        prefix = f"model.layers.{i}"
        tensor_map[f"{prefix}.self_attn.q_proj.weight"] = f"blk.{i}.attn_q.weight"
        tensor_map[f"{prefix}.self_attn.q_proj.bias"] = f"blk.{i}.attn_q.bias"
        tensor_map[f"{prefix}.self_attn.k_proj.weight"] = f"blk.{i}.attn_k.weight"
        tensor_map[f"{prefix}.self_attn.k_proj.bias"] = f"blk.{i}.attn_k.bias"
        tensor_map[f"{prefix}.self_attn.v_proj.weight"] = f"blk.{i}.attn_v.weight"
        tensor_map[f"{prefix}.self_attn.v_proj.bias"] = f"blk.{i}.attn_v.bias"
        tensor_map[f"{prefix}.self_attn.o_proj.weight"] = f"blk.{i}.attn_output.weight"
        tensor_map[f"{prefix}.mlp.gate_proj.weight"] = f"blk.{i}.ffn_gate.weight"
        tensor_map[f"{prefix}.mlp.up_proj.weight"] = f"blk.{i}.ffn_up.weight"
        tensor_map[f"{prefix}.mlp.down_proj.weight"] = f"blk.{i}.ffn_down.weight"
        tensor_map[f"{prefix}.input_layernorm.weight"] = f"blk.{i}.attn_norm.weight"
        tensor_map[f"{prefix}.post_attention_layernorm.weight"] = f"blk.{i}.ffn_norm.weight"
    
    # Add lm_head (tie_word_embeddings=true means it's shared with embed_tokens)
    if "lm_head.weight" in model:
        tensor_map["lm_head.weight"] = "output.weight"
    
    # Write tensors
    tensor_count = 0
    written_tensors = set()
    for name, tensor in model.items():
        if name in tensor_map:
            gguf_name = tensor_map[name]
            # Skip if already written (avoid duplicates from tie_word_embeddings)
            if gguf_name in written_tensors:
                continue
            written_tensors.add(gguf_name)
            # Convert to numpy array
            if isinstance(tensor, torch.Tensor):
                # Convert BF16 -> F32 -> F16 -> numpy
                if tensor.dtype == torch.bfloat16:
                    tensor = tensor.to(torch.float32).to(torch.float16)
                elif tensor.dtype == torch.float32:
                    tensor = tensor.to(torch.float16)
                tensor = tensor.numpy()
            print(f"  Writing {name} -> {gguf_name}")
            writer.add_tensor(gguf_name, tensor)
            tensor_count += 1
    
    # If tie_word_embeddings=true, add output.weight as copy of token_embd.weight
    if config.get("tie_word_embeddings", False) and "model.embed_tokens.weight" in model:
        embed_tensor = model["model.embed_tokens.weight"]
        if embed_tensor.dtype == torch.bfloat16:
            embed_tensor = embed_tensor.to(torch.float32).to(torch.float16)
        elif embed_tensor.dtype == torch.float32:
            embed_tensor = embed_tensor.to(torch.float16)
        embed_tensor = embed_tensor.numpy()
        print(f"  Writing model.embed_tokens.weight -> output.weight (tie_word_embeddings)")
        writer.add_tensor("output.weight", embed_tensor)
        tensor_count += 1
    
    print(f"Written {tensor_count} tensors")
    
    # Write all data
    try:
        writer.write_header_to_file()
        writer.write_kv_data_to_file()
        writer.write_tensors_to_file()
        writer.close()
        print("Writer closed successfully")
    except Exception as e:
        print(f"Error writing: {e}")
    
    # Verify file exists
    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"Done! GGUF model saved to {output_path}")
        print(f"Model size: {size_mb:.2f} MB")
    else:
        print(f"ERROR: File not found at {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert HuggingFace model to GGUF")
    parser.add_argument("model_path", help="Path to HuggingFace model")
    parser.add_argument("output_path", help="Output GGUF file path")
    parser.add_argument("--quant-type", default="f16", help="Quantization type (f16, q8_0, etc.)")
    
    args = parser.parse_args()
    convert_to_gguf(args.model_path, args.output_path, args.quant_type)
