import React, { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Stars, Sparkles } from '@react-three/drei';

// Lưới không gian trôi về phía camera
function MovingGrid() {
  const gridRef = useRef();

  useFrame((state) => {
    if (gridRef.current) {
      // Di chuyển lưới về phía trước
      gridRef.current.position.z = (state.clock.elapsedTime * 2) % 10;
    }
  });

  return (
    <group ref={gridRef} position={[0, -5, -20]}>
      <gridHelper args={[100, 100, '#8b5cf6', '#06b6d4']} position={[0, 0, 0]} />
    </group>
  );
}

// Hạt bụi năng lượng trôi nổi
function FloatingEnergy() {
  const groupRef = useRef();
  
  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = state.clock.elapsedTime * 0.05;
    }
  });

  return (
    <group ref={groupRef}>
      <Sparkles count={300} scale={30} size={4} speed={0.4} opacity={0.6} color="#22d3ee" />
      <Sparkles count={200} scale={20} size={6} speed={0.8} opacity={0.4} color="#8b5cf6" />
    </group>
  );
}

export default function CanvasBackground() {
  return (
    <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: -1, background: '#060611', pointerEvents: 'none' }}>
      <Canvas camera={{ position: [0, 2, 10], fov: 60 }} dpr={[1, 1.5]}>
        <fog attach="fog" args={['#060611', 10, 40]} />
        <ambientLight intensity={0.5} />
        
        <Stars radius={50} depth={50} count={3000} factor={4} saturation={1} fade speed={1} />
        <FloatingEnergy />
        <MovingGrid />
      </Canvas>
    </div>
  );
}
