document.addEventListener("DOMContentLoaded", function() {
  const videoFeed = document.getElementById('videoFeed');
  const snapshotContainer = document.getElementById('snapshot-container');
  const snapshotImg = document.getElementById('snapshot');
  const emotionText = document.getElementById('emotionText');
  const faceCanvas = document.getElementById('faceCanvas');
  const videoContainer = document.getElementById('video-container');
  const interactionVideo = document.getElementById('interactionVideo');

  const ctx = faceCanvas.getContext('2d');
  let currentEmotion = "neutral";
  let isAudioPlaying = false;

  let audioAnalyser = null;
  let audioDataArray = null;

  // --- Face Animation (draw a simple animated face) ---
  // Draw the face with dynamic eyes and a semi-oval mouth.
  function drawFace(emotion, mouthState = "neutral", amplitude = 0) {
    // Get current time (in seconds) for floating effect.
    const t = Date.now() / 1000;
    // Floating offset oscillates smoothly (e.g. ±10 pixels).
    const floatOffset = 20 * Math.sin(t * 0.6);
  
    // Clear the canvas.
    ctx.clearRect(0, 0, faceCanvas.width, faceCanvas.height);
  
    // --- Draw Eyes as Rectangles ---
    // Base positions for the eyes.
    let leftEyeX = 150, leftEyeY = 150 + floatOffset + 5;
    let rightEyeX = 240, rightEyeY = 150 + floatOffset;
    // Base dimensions for the rectangular eyes.
    let baseEyeWidth =25;       // fixed width
    let baseEyeHeight = 50;      // vertical dimension
    // When talking, adjust only the vertical dimension.
    const eyeHeightChangeFactor = 20; // maximum change in pixels.
    let adjustedEyeHeight = baseEyeHeight;
    if (mouthState === "talking") {
      adjustedEyeHeight = baseEyeHeight - (amplitude * eyeHeightChangeFactor);
      if (adjustedEyeHeight < 20) {  // ensure a minimum height
        adjustedEyeHeight = 20;
      }
    }
    ctx.fillStyle = "black";
    ctx.fillRect(leftEyeX, leftEyeY, baseEyeWidth, adjustedEyeHeight);
    ctx.fillRect(rightEyeX, rightEyeY, baseEyeWidth, adjustedEyeHeight);
  
    // --- Draw Mouth as a Semi-Oval ---
    // Base mouth center.
    const mouthCenterX = 200, mouthCenterY = 250 + floatOffset;
    // Base horizontal radius (half-width) for a neutral mouth.
    const baseMouthRadiusX = 35;
    // Base vertical radius for a neutral expression.
    const baseMouthRadiusY = 2;
    // When talking, adjust the vertical radius to simulate opening.
    const mouthOpenFactorY = 40; // maximum vertical increase.
    let adjustedMouthRadiusY = baseMouthRadiusY;
    // Also, adjust the horizontal radius based on amplitude.
    const mouthOpenFactorX = 30; // maximum horizontal increase.
    let adjustedMouthRadiusX = baseMouthRadiusX;
    
    if (mouthState === "talking") {
      adjustedMouthRadiusY = baseMouthRadiusY + amplitude * mouthOpenFactorY;
      adjustedMouthRadiusX = baseMouthRadiusX + amplitude * mouthOpenFactorX;
    } else if (mouthState === "happy") {
      // For happy or sad, you can set fixed values if desired.
      adjustedMouthRadiusY = baseMouthRadiusY; 
      adjustedMouthRadiusX = baseMouthRadiusX;
    } else if (mouthState === "sad") {
      adjustedMouthRadiusY = baseMouthRadiusY;
      adjustedMouthRadiusX = baseMouthRadiusX;
    }
    
    // Draw the bottom half of an ellipse (semi-oval) to represent the mouth.
    ctx.fillStyle = "red";
    ctx.beginPath();
    // Draw the bottom half using ctx.ellipse.
    ctx.ellipse(mouthCenterX, mouthCenterY, adjustedMouthRadiusX, adjustedMouthRadiusY, 0, 0, Math.PI, false);
    ctx.fill();
    ctx.strokeStyle = "black";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.closePath();
  }
  
  function animateFace() {
    let mouthState = "neutral";
    let mouthAmplitude = 0; // default amplitude value
    
    if (isAudioPlaying && audioAnalyser) {
      audioAnalyser.getByteFrequencyData(audioDataArray);
      let sum = 0;
      for (let i = 0; i < audioDataArray.length; i++) {
        sum += audioDataArray[i];
      }
      let avg = sum / audioDataArray.length;
      mouthAmplitude = avg / 255; // normalize amplitude (0 to 1)
      mouthState = "talking";
    } else if (currentEmotion === "happy") {
      mouthState = "happy";
    } else if (currentEmotion === "sad") {
      mouthState = "sad";
    }
    
    // Call the draw function with the computed parameters.
    drawFace(currentEmotion, mouthState, mouthAmplitude);
    requestAnimationFrame(animateFace);
  }
  

  
  
  animateFace();

  function setupAudioAnalyser(audioElement) {
    // Create an AudioContext (use webkitAudioContext for Safari)
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const track = audioContext.createMediaElementSource(audioElement);
    // Create an analyser node
    audioAnalyser = audioContext.createAnalyser();
    audioAnalyser.fftSize = 256;  // Smaller FFT size means faster updates but lower resolution
    const bufferLength = audioAnalyser.frequencyBinCount;
    audioDataArray = new Uint8Array(bufferLength);
    // Connect the audio element through the analyser to the output
    track.connect(audioAnalyser);
    audioAnalyser.connect(audioContext.destination);
  }

  // --- Poll Detection Status ---
  function pollDetectionStatus() {
    fetch('/detection_status')
      .then(res => res.json())
      .then(data => {
        if (data.detected) {
          clearInterval(pollInterval);
          currentEmotion = data.emotion;
          console.log("Detection complete. Emotion:", currentEmotion);
          // Hide the live video feed and show the snapshot container
          videoFeed.style.display = "none";
          snapshotContainer.style.display = "block";
          // Force a refresh of the snapshot image (avoid caching issues)
          const newSrc = "/snapshot?" + new Date().getTime();
          console.log("Setting snapshot image src to:", newSrc);
          snapshotImg.src = newSrc;
          emotionText.innerText = "Emotion: " + currentEmotion;
          // Trigger audio playback (which then triggers video, etc.)
          triggerAudio(currentEmotion);
        }
      })
      .catch(err => console.error("Error polling detection status:", err));
  }
  let pollInterval = setInterval(pollDetectionStatus, 1000);

  // --- Play Emotion-Specific Audio ---
  function triggerAudio(emotion) {
    fetch(`/get_random_audio?category=emotion&emotion=${emotion}`)
      .then(res => res.json())
      .then(data => {
        if(data.audio_url) {
          playAudio(data.audio_url)
            .then(() => {
              // After audio ends, play the interaction video
              triggerVideo();
            })
            .catch(err => console.error("Error playing audio:", err));
        } else {
          console.error("No audio file found for emotion:", emotion);
          // If no audio, proceed to video
          triggerVideo();
        }
      })
      .catch(err => console.error("Error fetching audio URL:", err));
  }
  
  function playAudio(url) {
    return new Promise((resolve, reject) => {
      const audio = new Audio(url);
      audio.onplay = () => {
        setupAudioAnalyser(audio);
      };
      isAudioPlaying = true;
      audio.play();
      audio.onended = () => {
        isAudioPlaying = false;
        audioAnalyser = null;  // Clear the analyser once audio stops
        resolve();
      };
      audio.onerror = reject;
    });
  }

  // --- Trigger Interaction Video ---
  function triggerVideo() {
    // Hide snapshot and canvas, then show video container
    document.getElementById('main-container').style.display = "none";
    videoContainer.style.display = "flex";  // Use "flex" for proper flexbox styling
    fetch('/get_random_video')
      .then(res => res.json())
      .then(data => {
        if(data.video_url) {
          interactionVideo.src = data.video_url;
          interactionVideo.play();
          interactionVideo.onended = () => {
            // After video finishes, restart the interaction
            restartInteraction();
          };
        } else {
          console.error("No video file found.");
          restartInteraction();
        }
      })
      .catch(err => console.error("Error fetching video URL:", err));
  }
  
  
  // --- Restart Interaction ---
  function restartInteraction() {
    fetch('/restart')
      .then(() => {
        // Reload the page (or reset UI elements) to start over
        location.reload();
      })
      .catch(err => console.error("Error restarting interaction:", err));
  }
});
