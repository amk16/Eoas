/**
 * AudioWorklet processor for converting audio to PCM16 format
 * This runs in a separate audio thread for better performance
 */
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 4096;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    
    if (input.length > 0) {
      const inputChannel = input[0];
      
      // Fill buffer with input samples
      for (let i = 0; i < inputChannel.length; i++) {
        this.buffer[this.bufferIndex++] = inputChannel[i];
        
        // When buffer is full, convert and send
        if (this.bufferIndex >= this.bufferSize) {
          // Convert Float32Array to Int16Array (s16le format)
          const int16Data = new Int16Array(this.bufferSize);
          for (let j = 0; j < this.bufferSize; j++) {
            // Clamp and convert to int16
            const s = Math.max(-1, Math.min(1, this.buffer[j]));
            int16Data[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          
          // Send to main thread
          this.port.postMessage({
            type: 'audioData',
            data: int16Data.buffer
          }, [int16Data.buffer]);
          
          // Reset buffer
          this.bufferIndex = 0;
        }
      }
    }
    
    // Return true to keep the processor alive
    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);

