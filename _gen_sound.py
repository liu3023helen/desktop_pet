import wave
import struct
import math

sample_rate = 44100

def generate_tone(freq, start_sample, num_samples):
    samples = []
    for i in range(num_samples):
        t = (start_sample + i) / sample_rate
        envelope = 1.0
        if i < num_samples * 0.1:
            envelope = i / (num_samples * 0.1)
        elif i > num_samples * 0.8:
            envelope = (num_samples - i) / (num_samples * 0.2)
        value = envelope * math.sin(2 * math.pi * freq * t)
        samples.append(value)
    return samples

# 第一个音符：C6 (1046.5 Hz)，持续0.2秒
n1 = int(sample_rate * 0.2)
samples1 = generate_tone(1046.5, 0, n1)

# 第二个音符：E6 (1318.5 Hz)，从0.25秒开始，持续0.2秒
n2 = int(sample_rate * 0.2)
samples2 = generate_tone(1318.5, int(sample_rate * 0.25), n2)

# 混合
total_samples = max(n1, int(sample_rate * 0.25) + n2)
final = [0.0] * total_samples
for i, s in enumerate(samples1):
    final[i] += s * 0.5
for i, s in enumerate(samples2):
    idx = int(sample_rate * 0.25) + i
    if idx < total_samples:
        final[idx] += s * 0.5

# 写入WAV
wav_path = 'assets/sounds/reminder.wav'
with wave.open(wav_path, 'w') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    for s in final:
        value = int(s * 32767.0)
        value = max(-32768, min(32767, value))
        wf.writeframes(struct.pack('<h', value))

print(f'Generated: {wav_path}, {total_samples/sample_rate:.2f}s')
