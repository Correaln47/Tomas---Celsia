document.addEventListener("DOMContentLoaded", function() {
  const videoFeed = document.getElementById('videoFeed');
  const snapshotContainer = document.getElementById('snapshot-container');
  const snapshotImg = document.getElementById('snapshot');
  const emotionText = document.getElementById('emotionText');
  const faceCanvas = document.getElementById('faceCanvas');
  const videoContainer = document.getElementById('video-container');
  const interactionVideo = document.getElementById('interactionVideo');
  const ctx = faceCanvas.getContext('2d');

  let currentEmotion = "neutral"; // Guarda la emoción detectada
  let isAudioPlaying = false;

  // Variables para el análisis de audio
  let audioContext = null; // Contexto de audio global
  let audioAnalyser = null;
  let audioDataArray = null;

  // --- Función de Dibujo de Cara (MODIFICADA) ---
  function drawFace(emotion, mouthState = "neutral", amplitude = 0) {
      const cw = faceCanvas.width;
      const ch = faceCanvas.height;

      // --- Parámetros de Dibujo (Ajusta estos valores según tu preferencia) ---
      const faceCenterX = cw / 2;
      const faceCenterY = ch / 2; // Centrar verticalmente también

      // Ojos (calculados desde el centro)
      const eyeOffsetY = ch * -0.15; // Qué tan arriba del centro están los ojos
      const eyeSeparation = cw * 0.3; // Separación horizontal entre centros de ojos
      const baseEyeWidth = cw * 0.1;   // Ancho del ojo
      const baseEyeHeight = ch * 0.1;  // Alto base del ojo
      const eyeHeightChangeFactor = baseEyeHeight * 0.4; // Cuánto cambia el alto al hablar

      // Boca (calculada desde el centro)
      const mouthOffsetY = ch * 0.15; // Qué tan abajo del centro está la boca
      const baseMouthRadiusX = cw * 0.18; // Radio horizontal base
      const baseMouthRadiusY = ch * 0.05; // Radio vertical base (boca cerrada)
      const mouthOpenFactorY = ch * 0.1;  // Cuánto se abre verticalmente al hablar
      const mouthWidenFactorX = cw * 0.05; // Cuánto se ensancha horizontalmente al hablar

      // Limpieza y Oscilación
      const t = Date.now() / 1000; // Tiempo para animación
      const floatOffset = 5 * Math.sin(t * 0.8); // Oscilación vertical más sutil
      ctx.clearRect(0, 0, cw, ch);

      // --- Dibujar Ojos ---
      ctx.fillStyle = "black";
      const leftEyeX = faceCenterX - eyeSeparation / 2 - baseEyeWidth / 2;
      const rightEyeX = faceCenterX + eyeSeparation / 2 - baseEyeWidth / 2;
      const eyeY = faceCenterY + eyeOffsetY + floatOffset - baseEyeHeight / 2;

      let adjustedEyeHeight = baseEyeHeight;
      if (mouthState === "talking") {
          // Hacer que los ojos se achiquen un poco al hablar, basado en amplitud
          adjustedEyeHeight = baseEyeHeight - (amplitude * eyeHeightChangeFactor);
          // Asegurar un tamaño mínimo
          adjustedEyeHeight = Math.max(adjustedEyeHeight, baseEyeHeight * 0.6);
      } else if (emotion === "surprise") {
           adjustedEyeHeight = baseEyeHeight * 1.2; // Ojos más grandes para sorpresa
      }
      // Añade más lógica para otras emociones si quieres cambiar los ojos

      ctx.fillRect(leftEyeX, eyeY, baseEyeWidth, adjustedEyeHeight);
      ctx.fillRect(rightEyeX, eyeY, baseEyeWidth, adjustedEyeHeight);

      // --- Dibujar Boca ---
      const mouthCenterX = faceCenterX;
      const mouthCenterY = faceCenterY + mouthOffsetY + floatOffset;

      let adjustedMouthRadiusY = baseMouthRadiusY;
      let adjustedMouthRadiusX = baseMouthRadiusX;
      let startAngle = 0;
      let endAngle = Math.PI; // Semicírculo inferior por defecto
      let drawStroke = false; // Si se dibuja solo contorno
      let drawFill = true;    // Si se dibuja relleno
      ctx.fillStyle = "red";  // Color de relleno por defecto
      ctx.strokeStyle = "black"; // Color de contorno por defecto
      ctx.lineWidth = Math.max(2, cw * 0.005); // Grosor línea

      if (mouthState === "talking") {
          adjustedMouthRadiusY = baseMouthRadiusY + amplitude * mouthOpenFactorY;
          adjustedMouthRadiusX = baseMouthRadiusX + amplitude * mouthWidenFactorX;
          // Asegurarse que no sea demasiado pequeño al hablar bajo
          adjustedMouthRadiusY = Math.max(adjustedMouthRadiusY, baseMouthRadiusY * 0.5);
          adjustedMouthRadiusX = Math.max(adjustedMouthRadiusX, baseMouthRadiusX * 0.8);
      } else if (emotion === "happy") {
          // Boca sonriente (arco hacia arriba)
          startAngle = Math.PI; // Empezar desde abajo
          endAngle = 0;         // Terminar arriba
          adjustedMouthRadiusX = baseMouthRadiusX * 1.1; // Un poco más ancha
          adjustedMouthRadiusY = baseMouthRadiusY * 1.5; // Más curvada
          drawStroke = true; // Solo contorno para sonrisa
          drawFill = false;
          ctx.strokeStyle = "red"; // Contorno rojo para sonrisa
          ctx.lineWidth = Math.max(3, cw * 0.01); // Línea más gruesa
      } else if (emotion === "sad") {
          // Boca triste (arco hacia abajo)
          startAngle = 0;
          endAngle = Math.PI;
          adjustedMouthRadiusX = baseMouthRadiusX * 0.9; // Un poco más estrecha
          adjustedMouthRadiusY = baseMouthRadiusY * 1.3; // Más curvada hacia abajo
          drawStroke = true; // Solo contorno
          drawFill = false;
          ctx.strokeStyle = "blue"; // Contorno azul para tristeza
          ctx.lineWidth = Math.max(3, cw * 0.01);
      } else if (emotion === "surprise") {
           // Boca abierta (óvalo completo)
           startAngle = 0;
           endAngle = Math.PI * 2; // Círculo completo
           adjustedMouthRadiusX = baseMouthRadiusX * 0.8;
           adjustedMouthRadiusY = baseMouthRadiusY * 2.5; // Bastante abierta verticalmente
           ctx.fillStyle = "black"; // Relleno negro para boca abierta
      } else if (emotion === "angry") {
           // Boca tensa (línea recta o ligeramente curvada hacia abajo)
           startAngle = 0;
           endAngle = Math.PI;
           adjustedMouthRadiusX = baseMouthRadiusX * 1.1; // Ancha
           adjustedMouthRadiusY = baseMouthRadiusY * 0.3; // Muy plana
           drawStroke = true;
           drawFill = false;
           ctx.strokeStyle = "darkred";
           ctx.lineWidth = Math.max(4, cw * 0.015);
      }
      // Añadir más 'else if' para fear, disgust, neutral si quieres algo específico

      // Dibujar la boca
      ctx.beginPath();
      // Usar ellipse para flexibilidad
      // El último parámetro es anticlockwise (afecta si start/end son > PI)
      ctx.ellipse(mouthCenterX, mouthCenterY, adjustedMouthRadiusX, adjustedMouthRadiusY, 0, startAngle, endAngle, (emotion === 'happy'));

      if (drawFill) {
          ctx.fill();
      }
      if (drawStroke) {
           // Si también hay relleno, dibuja el contorno encima
           if(drawFill) {
               ctx.strokeStyle = "black"; // Contorno negro sobre relleno rojo
               ctx.lineWidth = 2;
               ctx.stroke();
           } else {
               // Si no hay relleno, solo dibuja el contorno con su color/grosor
               ctx.stroke();
           }
      } else if(drawFill && emotion !== 'surprise') {
           // Añadir contorno negro por defecto si hay relleno y no es sorpresa (boca negra)
           ctx.strokeStyle = "black";
           ctx.lineWidth = 2;
           ctx.stroke();
      }
      ctx.closePath();
  }

  // --- Función de Animación (MODIFICADA) ---
  function animateFace() {
      let mouthState = "neutral"; // Estado base
      let mouthAmplitude = 0;     // Amplitud base

      if (isAudioPlaying && audioAnalyser && audioDataArray) {
          // Asegúrate de que el contexto de audio esté activo
          if (audioContext && audioContext.state === 'running') {
              audioAnalyser.getByteFrequencyData(audioDataArray);
              let sum = audioDataArray.reduce((a, b) => a + b, 0);
              let avg = audioDataArray.length > 0 ? sum / audioDataArray.length : 0;
              // Normalizar amplitud (0-255) a un rango útil (ej. 0-1)
              // El valor 128 es un punto medio, ajusta el divisor si es necesario
              mouthAmplitude = avg / 128;
              mouthAmplitude = Math.min(1.5, Math.max(0, mouthAmplitude)); // Limitar entre 0 y 1.5 (permite exagerar un poco)
              mouthState = "talking";
          } else {
               // Si el contexto no está activo, no procesar audio
               mouthState = currentEmotion; // Mantener emoción estática
          }
      } else {
          // No está hablando, usar la emoción actual para el estado
          mouthState = currentEmotion; // Pasar la emoción detectada
      }

      // Llamar a drawFace con la emoción, estado y amplitud
      // Pasamos currentEmotion para que sepa qué cara base dibujar
      drawFace(currentEmotion, mouthState, mouthAmplitude);
      requestAnimationFrame(animateFace); // Solicitar el siguiente frame
  }

  // --- Configuración del Analizador de Audio (MODIFICADA) ---
  function setupAudioAnalyser(audioElement) {
      // Crear contexto sólo si no existe o está cerrado
      if (!audioContext || audioContext.state === 'closed') {
          audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }

      // Reanudar contexto si está suspendido (requiere interacción del usuario a veces)
      if (audioContext.state === 'suspended') {
          audioContext.resume();
      }

      // Sólo proceder si el contexto está activo
      if (audioContext.state === 'running') {
          try {
              const track = audioContext.createMediaElementSource(audioElement);
              audioAnalyser = audioContext.createAnalyser();
              audioAnalyser.fftSize = 256; // Tamaño FFT (potencia de 2)
              const bufferLength = audioAnalyser.frequencyBinCount; // Será la mitad de fftSize
              audioDataArray = new Uint8Array(bufferLength); // Crear array para datos

              // Conectar nodos: source -> analyser -> destination
              track.connect(audioAnalyser);
              audioAnalyser.connect(audioContext.destination);
              console.log("Audio Analyser configurado.");
          } catch (e) {
               console.error("Error configurando Audio Analyser:", e);
               // Puede fallar si el elemento ya tiene un source node
               // O si el contexto no se pudo reanudar.
               audioAnalyser = null;
               audioDataArray = null;
          }
      } else {
          console.warn("AudioContext no está activo. No se puede configurar Analyser.");
          audioAnalyser = null;
          audioDataArray = null;
      }
  }


  // --- Reproducción de Audio (MODIFICADA) ---
  function playAudio(url) {
      return new Promise((resolve, reject) => {
          const audio = new Audio(url);

          // IMPORTANTE: Intentar configurar el analizador en 'onplay'
          // Es más probable que el contexto de audio esté listo aquí.
          audio.onplay = () => {
              console.log("Audio onplay event triggered.");
              // Intentar configurar o reconfigurar el analizador
              setupAudioAnalyser(audio);
              isAudioPlaying = true; // Marcar como reproduciendo AQUI
          };

          // Intentar reproducir
          audio.play().then(() => {
              console.log("Audio playback iniciada para:", url);
              // isAudioPlaying = true; // NO aquí, esperar a onplay
          }).catch(e => {
              console.error("Error al iniciar audio automáticamente:", e);
              isAudioPlaying = false;
              // Podrías intentar reanudar el contexto aquí si falla por interacción
              if (audioContext && audioContext.state === 'suspended') {
                  console.log("Intentando reanudar AudioContext...");
                  audioContext.resume().then(() => {
                       console.log("AudioContext reanudado, reintentando play...");
                       audio.play().catch(e2 => reject(e2)); // Reintentar play
                  }).catch(resumeError => {
                      console.error("Error reanudando AudioContext:", resumeError);
                      reject(e); // Rechazar con el error original de play
                  });
              } else {
                  reject(e); // Rechazar si no es un problema de suspensión
              }
          });

          // Al terminar
          audio.onended = () => {
              console.log("Audio onended event triggered.");
              isAudioPlaying = false;
              // Desconectar o limpiar recursos si es necesario, aunque a menudo no hace falta
              // audioAnalyser?.disconnect(); // Opcional
              audioAnalyser = null;
              audioDataArray = null; // Limpiar el array
              resolve(); // Resolver la promesa
          };

          // En caso de error
          audio.onerror = (e) => {
              console.error("Error durante la reproducción de audio:", e);
              isAudioPlaying = false;
              audioAnalyser = null;
              audioDataArray = null;
              reject(e); // Rechazar la promesa
          };
      });
  }


  // --- Poll Detection Status ---
  function pollDetectionStatus() {
      fetch('/detection_status')
          .then(res => res.json())
          .then(data => {
              if (data.detected) {
                  clearInterval(pollInterval);
                  currentEmotion = data.emotion; // Actualizar emoción global
                  console.log("Detection complete. Emotion:", currentEmotion);
                  videoFeed.style.display = "none";
                  snapshotContainer.style.display = "block";
                  const newSrc = "/snapshot?" + new Date().getTime();
                  console.log("Setting snapshot image src to:", newSrc);
                  snapshotImg.src = newSrc;
                  emotionText.innerText = "Emoción Detectada: " + currentEmotion; // Texto más claro
                  // Forzar un redibujo de la cara con la emoción final antes de audio/video
                  drawFace(currentEmotion, currentEmotion, 0);
                  triggerAudio(currentEmotion);
              } else {
                   // Mientras no detecta, mantener la cara neutral
                   // O podrías intentar mostrar la última emoción detectada si la tuvieras
                   currentEmotion = "neutral"; // Opcional: resetear si no hay detección estable
                   // drawFace("neutral", "neutral", 0); // Dibuja neutral si no hay detección
              }
          })
          .catch(err => {
              console.error("Error polling detection status:", err);
              // Considera qué hacer si falla el polling, ¿resetear emoción?
              currentEmotion = "neutral";
              // drawFace("neutral", "neutral", 0);
          });
  }
  let pollInterval = setInterval(pollDetectionStatus, 1000); // Revisa cada segundo

  // --- Play Emotion-Specific Audio ---
  function triggerAudio(emotion) {
      console.log(`Triggering audio for emotion: ${emotion}`);
      fetch(`/get_random_audio?emotion=${emotion}`) // Asumiendo que la ruta solo necesita la emoción
          .then(res => {
               if (!res.ok) { throw new Error(`HTTP error! status: ${res.status}`); }
               return res.json();
          })
          .then(data => {
              if (data.audio_url) {
                  console.log(`Audio URL received: ${data.audio_url}`);
                  playAudio(data.audio_url)
                      .then(() => {
                          console.log("Audio playback finished.");
                          triggerVideo(); // Reproducir video después del audio
                      })
                      .catch(err => {
                           console.error("Error playing audio:", err);
                           triggerVideo(); // Ir al video incluso si el audio falla
                       });
              } else {
                  console.error("No audio file found for emotion:", emotion, "Response:", data);
                  triggerVideo(); // Si no hay URL de audio, ir directo al video
              }
          })
          .catch(err => {
               console.error("Error fetching audio URL:", err);
               triggerVideo(); // Ir al video si hay error buscando audio
           });
  }

  // --- Trigger Interaction Video ---
  function triggerVideo() {
      console.log("Triggering video playback.");
      // Ocultar contenedor principal (snapshot y canvas)
      document.getElementById('main-container').style.display = "none";
      // Mostrar contenedor de video
      videoContainer.style.display = "flex"; // Usar flex si así está en CSS

      fetch('/get_random_video')
           .then(res => {
               if (!res.ok) { throw new Error(`HTTP error! status: ${res.status}`); }
               return res.json();
           })
          .then(data => {
              if (data.video_url) {
                  console.log(`Video URL received: ${data.video_url}`);
                  interactionVideo.src = data.video_url;
                  interactionVideo.play().then(() => {
                      console.log("Video playback started.");
                  }).catch(e => {
                       console.error("Error starting video playback:", e);
                       restartInteraction(); // Reiniciar si el video no puede empezar
                   });

                  // Evento para cuando el video termine
                  interactionVideo.onended = () => {
                      console.log("Video playback finished.");
                      restartInteraction(); // Reiniciar al terminar el video
                  };
              } else {
                  console.error("No video file found. Response:", data);
                  restartInteraction(); // Reiniciar si no hay URL de video
              }
          })
          .catch(err => {
               console.error("Error fetching video URL:", err);
               restartInteraction(); // Reiniciar si hay error buscando video
           });
  }

  // --- Restart Interaction ---
  function restartInteraction() {
      console.log("Restarting interaction...");
      fetch('/restart')
          .then(res => res.json())
          .then(data => {
              console.log("Restart signal sent to server:", data);
              // Recargar la página es la forma más simple de reiniciar el estado del cliente
              location.reload();
          })
          .catch(err => {
              console.error("Error sending restart signal:", err);
              // Intentar recargar igualmente
              location.reload();
          });
  }

  // --- Inicialización al cargar la página ---
  // Asegúrate que el canvas tenga tamaño antes de dibujar
  // Puedes setearlo aquí o asegurarte que esté en el CSS
  // faceCanvas.width = 600; // Ejemplo
  // faceCanvas.height = 450; // Ejemplo
  console.log("Document loaded. Initializing face animation.");
  drawFace("neutral", "neutral", 0); // Dibujar estado inicial neutral
  animateFace(); // Iniciar el bucle de animación

}); // Fin de DOMContentLoaded