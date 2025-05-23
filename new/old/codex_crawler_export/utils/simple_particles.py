import streamlit as st

def add_simple_particles():
    """Add a simple particle effect that works within Streamlit's sandbox limitations"""
    
    # Add CSS and HTML for a simple canvas-based particle system
    st.markdown("""
    <style>
    #particles-canvas {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: -1;
    }
    
    .stApp {
        background: transparent !important;
    }
    
    .main .block-container {
        background: rgba(14, 17, 23, 0.7) !important;
    }
    </style>
    
    <canvas id="particles-canvas"></canvas>
    
    <script>
    // A simple particle system that works with Streamlit's iframe sandbox
    (function() {
        const canvas = document.getElementById('particles-canvas');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        const particles = [];
        let mouseX = 0;
        let mouseY = 0;
        let lastMouseX = 0;
        let lastMouseY = 0;
        
        // Track mouse position
        document.addEventListener('mousemove', function(e) {
            mouseX = e.clientX;
            mouseY = e.clientY;
        });
        
        // Resize canvas to match window
        function resizeCanvas() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
        
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
        
        // Particle class
        class Particle {
            constructor() {
                this.reset();
            }
            
            reset() {
                this.x = Math.random() * canvas.width;
                this.y = Math.random() * canvas.height;
                this.size = Math.random() * 3 + 1;
                this.speedX = Math.random() * 2 - 1;
                this.speedY = Math.random() * 2 - 1;
                this.color = `rgba(63, 204, 102, ${Math.random() * 0.5 + 0.25})`;
            }
            
            update() {
                // Move particles
                this.x += this.speedX;
                this.y += this.speedY;
                
                // Wrap around edges
                if (this.x < 0 || this.x > canvas.width || 
                    this.y < 0 || this.y > canvas.height) {
                    this.reset();
                }
                
                // React to mouse if close enough
                const dx = mouseX - this.x;
                const dy = mouseY - this.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                if (distance < 100) {
                    // Push away from mouse
                    this.x -= dx * 0.02;
                    this.y -= dy * 0.02;
                }
            }
            
            draw() {
                ctx.fillStyle = this.color;
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
                ctx.fill();
            }
            
            connect() {
                // Connect particles with lines when close enough
                for (let i = 0; i < particles.length; i++) {
                    const other = particles[i];
                    if (this === other) continue;
                    
                    const dx = this.x - other.x;
                    const dy = this.y - other.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    
                    if (distance < 100) {
                        const opacity = (100 - distance) / 100 * 0.8;
                        ctx.strokeStyle = `rgba(0, 217, 255, ${opacity})`;
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        ctx.moveTo(this.x, this.y);
                        ctx.lineTo(other.x, other.y);
                        ctx.stroke();
                    }
                }
            }
        }
        
        // Create particles
        function initParticles() {
            for (let i = 0; i < 75; i++) {
                particles.push(new Particle());
            }
        }
        
        // Animation loop
        function animate() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Draw a subtle gradient background
            const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
            gradient.addColorStop(0, '#0e1117');
            gradient.addColorStop(1, '#111820');
            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Update and draw particles
            for (let i = 0; i < particles.length; i++) {
                particles[i].update();
                particles[i].draw();
            }
            
            // Draw connections
            for (let i = 0; i < particles.length; i++) {
                particles[i].connect();
            }
            
            // Remember mouse position for next frame
            lastMouseX = mouseX;
            lastMouseY = mouseY;
            
            requestAnimationFrame(animate);
        }
        
        // Start animation
        initParticles();
        animate();
    })();
    </script>
    """, unsafe_allow_html=True)