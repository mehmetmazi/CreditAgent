import os
import sys

try:
    from anthropic import Anthropic
except Exception as e:
    print("anthropic SDK not installed or failed to import:", e)
    sys.exit(2)


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set in the environment. Set it and re-run this script.")
        print("Example: export ANTHROPIC_API_KEY=\"sk-...\"")
        return

    client = Anthropic(api_key=api_key)

    prompt = (
        "Write a concise (2-3 sentence) professional summary of Apple Inc., "
        "using only public facts.\n\n" 
        "Return the answer as plain text."
    )

    try:
        # Note: SDKs and API signatures may vary by version. This call matches common patterns.
        resp = client.completions.create(
            model="claude-2",  # adjust if you have a different model in your account
            prompt=prompt,
            max_tokens_to_sample=300,
        )
        # Try a couple of common response attributes
        if hasattr(resp, "completion"):
            print(resp.completion)
        elif hasattr(resp, "output_text"):
            print(resp.output_text)
        else:
            print(resp)
    except Exception as e:
        print("Error while calling Anthropic API:", type(e).__name__, e)


if __name__ == "__main__":
    main()

