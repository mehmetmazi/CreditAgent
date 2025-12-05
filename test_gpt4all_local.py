from gpt4all import GPT4All

# start with a small-ish model so your Mac doesn't die
MODEL_NAME = "Meta-Llama-3.2-3B-Instruct.Q4_0.gguf"  # ~1.8GB; good for CPU-only

def main():
    model = GPT4All(MODEL_NAME)  # first run will download the model
    with model.chat_session():
        reply = model.generate(
            "In one or two sentences, explain what a credit analyst does.",
            max_tokens=80,
            temp=0.2,
        )
    print("MODEL REPLY:\n", reply)

if __name__ == "__main__":
    main()
