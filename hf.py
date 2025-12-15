from huggingface_hub import InferenceClient
client = InferenceClient(token=HF_TOKEN)
print(client.get_models())
