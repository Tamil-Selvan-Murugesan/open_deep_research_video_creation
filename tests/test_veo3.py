import time
from google import genai
from google.genai import types

client = genai.Client(api_key='*****')

# prompt = """A close up of two people staring at a cryptic drawing on a wall, torchlight flickering.
# A man murmurs, 'This must be it. That's the secret code.' The woman looks at him and whispering excitedly, 'What did you find?'"""

prompt = """
High-energy montage, TV hosts laughing about Norris, teenagers quoting memes at school, ads referencing Norris’s toughness. Vivid kinetic editing echoes meme virality and real-world impact.
"""
operation = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt=prompt,
)

# Poll the operation status until the video is ready.
while not operation.done:
    print("Waiting for video generation to complete...")
    time.sleep(10)
    operation = client.operations.get(operation)

# Download the generated video.
generated_video = operation.response.generated_videos[0]
client.files.download(file=generated_video.video)
generated_video.video.save("2005-2.mp4")
print("Generated video saved to 2005-2.mp4")