import gpt4all

# Initialize the GPT4All model.
# This will download the model file if it doesn't exist.
model = gpt4all.GPT4All("orca-mini-7b.ggmlv3.q4_0.bin")

# Start a new chat session
with model.chat_session():
    # Generate a response to a prompt
    response = model.generate("What is the capital of France?")
    print(response)

    # You can continue the chat within the same session
    response = model.generate("Tell me more about it.")
    print(response)

    # View the chat history (optional)
    print(model.current_chat_session)
