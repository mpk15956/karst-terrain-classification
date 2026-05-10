import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Configuration constants
const CONFIG = {
    VERTICAL_SCALE: 10,
    WATER_COLOR: 0x4A90E2,
    TERRAIN_COLOR: 0x8B7355,
    INITIAL_CAMERA_DISTANCE: 30,
    BARCODE_DEBOUNCE_MS: 16,
    FALLBACK_TIMEOUT_MS: 5000
};

// Global state
let scene, camera, renderer, controls;
let terrainMesh, waterMesh;
let demData, filtrationData, metadata;
let waterLevel = 0;
let barcodeCanvas, barcodeCtx;

// Initialize scene
function init() {
    // Validate DOM elements exist
    const container = document.getElementById('canvas-container');
    if (!container) {
        console.error('[TDA_VIZ]: Canvas container not found');
        return;
    }

    barcodeCanvas = document.getElementById('barcode-canvas');
    if (!barcodeCanvas) {
        console.error('[TDA_VIZ]: Barcode canvas not found');
        return;
    }

    // Create scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a1a);

    // Create camera
    camera = new THREE.PerspectiveCamera(
        75,
        container.clientWidth / container.clientHeight,
        0.1,
        1000
    );
    camera.position.set(
        CONFIG.INITIAL_CAMERA_DISTANCE,
        CONFIG.INITIAL_CAMERA_DISTANCE,
        CONFIG.INITIAL_CAMERA_DISTANCE
    );
    camera.lookAt(0, 0, 0);

    // Create renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    // Add controls
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 10;
    controls.maxDistance = 100;

    // Add lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(20, 30, 20);
    directionalLight.castShadow = true;
    scene.add(directionalLight);

    // Initialize barcode canvas
    barcodeCtx = barcodeCanvas.getContext('2d');
    if (!barcodeCtx) {
        console.error('[TDA_VIZ]: Failed to get 2D context from barcode canvas');
        return;
    }
    resizeBarcodeCanvas();

    // Show loading indicator (append as overlay, don't replace renderer)
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loading-indicator';
    loadingDiv.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        text-align: center;
        background: #1a1a1a;
        z-index: 1000;
    `;
    loadingDiv.innerHTML = `
        <div>
            <div style="font-size: 18px; margin-bottom: 10px;">Loading visualization...</div>
            <div style="font-size: 12px; color: #999;">Loading terrain data</div>
        </div>
    `;
    container.appendChild(loadingDiv);

    // Load data
    loadData().then(() => {
        // Remove loading indicator
        const loading = document.getElementById('loading-indicator');
        if (loading) {
            loading.remove();
        }
        
        try {
            createTerrain();
            createWater();
            setupControls();
            animate();
        } catch (error) {
            console.error('[TDA_VIZ]: Failed to create scene:', error);
            // Show error in UI
            const errorContainer = document.getElementById('canvas-container');
            if (errorContainer) {
                errorContainer.innerHTML = `
                    <div style="display: flex; align-items: center; justify-content: center; 
                                height: 100%; color: #ff6b6b; text-align: center; padding: 20px; background: #1a1a1a;">
                        <div>
                            <h3 style="margin-bottom: 10px;">Scene Creation Failed</h3>
                            <p style="margin-bottom: 10px;">Could not create 3D visualization.</p>
                            <p style="font-size: 0.9em; color: #999;">
                                Error: ${error.message}
                            </p>
                        </div>
                    </div>
                `;
            }
        }
    }).catch((error) => {
        // Error already handled in loadData(), but catch here to prevent unhandled rejection
        console.error('[TDA_VIZ]: Unhandled error in initialization:', error);
    });
}

// Load JSON data
async function loadData() {
    try {
        const [demResponse, filtrationResponse, metadataResponse] = await Promise.all([
            fetch('data/hero_patch_dem.json'),
            fetch('data/filtration_data.json'),
            fetch('data/metadata.json')
        ]);

        // Check if responses are OK
        if (!demResponse.ok || !filtrationResponse.ok || !metadataResponse.ok) {
            throw new Error(`HTTP error: ${demResponse.status} ${filtrationResponse.status} ${metadataResponse.status}`);
        }

        demData = await demResponse.json();
        filtrationData = await filtrationResponse.json();
        metadata = await metadataResponse.json();

        // Validate data structure
        if (!demData || !Array.isArray(demData) || demData.length === 0) {
            throw new Error('DEM data is missing or invalid');
        }
        if (!metadata || !metadata.patch_size) {
            throw new Error('Metadata is missing or invalid');
        }
        if (demData.length !== metadata.patch_size || 
            (demData[0] && demData[0].length !== metadata.patch_size)) {
            throw new Error(
                `DEM size mismatch: expected ${metadata.patch_size}×${metadata.patch_size}, ` +
                `got ${demData.length}×${demData[0]?.length || 0}`
            );
        }
        if (!Array.isArray(filtrationData)) {
            throw new Error('Filtration data is not an array');
        }

        console.log('[TDA_VIZ]: ✓ Data loaded:', {
            demShape: `${demData.length}×${demData[0].length}`,
            nFeatures: filtrationData.length,
            metadata
        });
    } catch (error) {
        console.error('[TDA_VIZ]: Failed to load data:', error);
        
        // Show user-friendly error message
        const container = document.getElementById('canvas-container');
        if (container) {
            container.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; 
                            height: 100%; color: #ff6b6b; text-align: center; padding: 20px; background: #1a1a1a;">
                    <div>
                        <h3 style="margin-bottom: 10px;">Data Loading Failed</h3>
                        <p style="margin-bottom: 10px;">Could not load visualization data.</p>
                        <p style="font-size: 0.9em; color: #999; margin-bottom: 10px;">
                            Please run <code>export_viz_data.ipynb</code> first to generate the data files.
                        </p>
                        <p style="font-size: 0.8em; color: #666;">
                            Error: ${error.message}
                        </p>
                    </div>
                </div>
            `;
        }
        throw error;
    }
}

// Create terrain mesh
function createTerrain() {
    if (!demData || !Array.isArray(demData) || demData.length === 0) {
        throw new Error('[TDA_VIZ]: DEM data is missing or invalid');
    }
    if (!metadata || !metadata.patch_size) {
        throw new Error('[TDA_VIZ]: Metadata is missing or invalid');
    }

    const patchSize = metadata.patch_size || 50;
    const width = patchSize;
    const height = patchSize;
    const segments = patchSize - 1;

    // Create geometry
    const geometry = new THREE.PlaneGeometry(width, height, segments, segments);

    // Apply elevation displacement
    const positions = geometry.attributes.position;
    const scale = CONFIG.VERTICAL_SCALE;
    const verticesPerRow = segments + 1;

    for (let i = 0; i < positions.count; i++) {
        // PlaneGeometry vertices are laid out row by row
        const row = Math.floor(i / verticesPerRow);
        const col = i % verticesPerRow;
        
        if (row < patchSize && col < patchSize) {
            // DEM data is [row][col], where row is Y (vertical) and col is X (horizontal)
            const elevation = demData[row][col];
            positions.setY(i, elevation * scale);
        }
    }

    geometry.computeVertexNormals();

    // Create material
    const material = new THREE.MeshStandardMaterial({
        color: CONFIG.TERRAIN_COLOR,
        flatShading: true,
        metalness: 0.1,
        roughness: 0.8
    });

    // Create mesh
    terrainMesh = new THREE.Mesh(geometry, material);
    terrainMesh.rotation.x = -Math.PI / 2;
    scene.add(terrainMesh);

    // Add wireframe for better topology visibility
    const wireframe = new THREE.WireframeGeometry(geometry);
    const wireframeLine = new THREE.LineSegments(
        wireframe,
        new THREE.LineBasicMaterial({ color: 0x000000, opacity: 0.2, transparent: true })
    );
    wireframeLine.rotation.x = -Math.PI / 2;
    scene.add(wireframeLine);
}

// Create water plane
function createWater() {
    const patchSize = metadata.patch_size || 50;
    const geometry = new THREE.PlaneGeometry(patchSize, patchSize, 1, 1);
    
    const material = new THREE.MeshPhysicalMaterial({
        color: CONFIG.WATER_COLOR,
        transmission: 0.9,
        opacity: 0.5,
        roughness: 0.1,
        metalness: 0.0,
        transparent: true
    });

    waterMesh = new THREE.Mesh(geometry, material);
    waterMesh.rotation.x = -Math.PI / 2;
    
    // Position at minimum elevation initially
    const minElevation = 0; // Normalized, so min is 0
    waterMesh.position.y = minElevation * CONFIG.VERTICAL_SCALE;
    scene.add(waterMesh);
}

// Setup UI controls
function setupControls() {
    const slider = document.getElementById('slider');
    const waterLevelDisplay = document.getElementById('water-level');

    if (!slider || !waterLevelDisplay) {
        console.error('[TDA_VIZ]: Control elements not found');
        return;
    }

    // Debounce barcode redraw for performance
    let barcodeTimeout;
    
    slider.addEventListener('input', (e) => {
        waterLevel = parseFloat(e.target.value);
        updateWaterLevel(waterLevel);
        waterLevelDisplay.textContent = waterLevel.toFixed(2);
        
        // Debounce barcode redraw (update at ~60fps max)
        clearTimeout(barcodeTimeout);
        barcodeTimeout = setTimeout(() => drawBarcode(), CONFIG.BARCODE_DEBOUNCE_MS);
    });

    // Initial barcode draw
    drawBarcode();
}

// Update water level
function updateWaterLevel(level) {
    if (!waterMesh) {
        console.error('[TDA_VIZ]: Water mesh not initialized');
        return;
    }
    
    const scale = CONFIG.VERTICAL_SCALE;
    const minElevation = 0;
    const maxElevation = 1;
    const elevation = minElevation + level * (maxElevation - minElevation);
    waterMesh.position.y = elevation * scale;
}

// Draw barcode diagram
function drawBarcode() {
    const container = document.getElementById('barcode-container');
    if (!container || !barcodeCanvas || !barcodeCtx) return;
    
    // Use logical dimensions (not pixel dimensions) since context is already scaled by DPR
    const width = container.clientWidth;
    const height = container.clientHeight;
    const ctx = barcodeCtx;

    // Clear canvas (use logical dimensions since context is scaled)
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, width, height);

    if (!filtrationData || filtrationData.length === 0) {
        ctx.fillStyle = '#ffffff';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No persistence features', width / 2, height / 2);
        return;
    }

    // Find min/max birth/death for scaling
    let minBirth = Infinity;
    let maxDeath = -Infinity;
    filtrationData.forEach(f => {
        minBirth = Math.min(minBirth, f.birth);
        maxDeath = Math.max(maxDeath, f.death);
    });

    const range = maxDeath - minBirth;
    if (range === 0) {
        // All features have same birth/death (edge case)
        ctx.fillStyle = '#ffffff';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No variation in persistence', width / 2, height / 2);
        return;
    }

    const padding = 40;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    // Ensure barHeight is at least 1 pixel, prevent division by zero
    const barHeight = Math.max(1, Math.min(20, chartHeight / Math.max(1, filtrationData.length)));

    // Draw features
    filtrationData.forEach((feature, index) => {
        const y = padding + index * (barHeight + 2);
        const birthX = padding + ((feature.birth - minBirth) / range) * chartWidth;
        const deathX = padding + ((feature.death - minBirth) / range) * chartWidth;
        const barWidth = Math.max(1, deathX - birthX); // Ensure minimum width

        // Color by dimension
        if (feature.dim === 0) {
            ctx.fillStyle = '#FF6B6B'; // Red for peaks
        } else if (feature.dim === 1) {
            ctx.fillStyle = '#4ECDC4'; // Teal for holes
        } else {
            ctx.fillStyle = '#95A5A6'; // Gray for others
        }

        // Draw bar
        ctx.fillRect(birthX, y, barWidth, barHeight);

        // Draw current time line
        // Map waterLevel (0-1 normalized elevation) to filtration parameter space
        // Since persistence diagram is computed on normalized elevation, this mapping is correct
        const currentTime = minBirth + waterLevel * range;
        if (currentTime >= feature.birth && currentTime <= feature.death) {
            ctx.strokeStyle = '#FFD93D';
            ctx.lineWidth = 2;
            ctx.beginPath();
            const lineX = padding + ((currentTime - minBirth) / range) * chartWidth;
            ctx.moveTo(lineX, y);
            ctx.lineTo(lineX, y + barHeight);
            ctx.stroke();
        }
    });

    // Draw axes
    ctx.strokeStyle = '#666666';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();

    // Draw labels
    ctx.fillStyle = '#ffffff';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Birth', padding, height - 10);
    ctx.fillText('Death', width - padding, height - 10);
    ctx.textAlign = 'left';
    ctx.fillText('Filtration Parameter', width / 2 - 60, height - 10);
}

// Resize barcode canvas
function resizeBarcodeCanvas() {
    const container = document.getElementById('barcode-container');
    if (!container || !barcodeCanvas) return;
    
    // Set display size
    barcodeCanvas.style.width = container.clientWidth + 'px';
    barcodeCanvas.style.height = container.clientHeight + 'px';
    
    // Set actual resolution (for high-DPI displays)
    const dpr = window.devicePixelRatio || 1;
    barcodeCanvas.width = container.clientWidth * dpr;
    barcodeCanvas.height = container.clientHeight * dpr;
    
    // Re-get context if lost, or get it for the first time
    if (!barcodeCtx) {
        barcodeCtx = barcodeCanvas.getContext('2d');
        if (!barcodeCtx) {
            console.error('[TDA_VIZ]: Failed to get 2D context from barcode canvas');
            return;
        }
    }
    
    // Reset transform and scale for high-DPI (prevents cumulative scaling)
    barcodeCtx.setTransform(1, 0, 0, 1, 0, 0); // Reset to identity
    barcodeCtx.scale(dpr, dpr);
}

// Animation loop
function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}

// Handle window resize
window.addEventListener('resize', () => {
    const container = document.getElementById('canvas-container');
    if (!container || !camera || !renderer) return;
    
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
    resizeBarcodeCanvas();
    drawBarcode();
});

// Initialize on load
init();

