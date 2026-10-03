import React, { useRef, useState, useEffect, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html, Float } from '@react-three/drei';
import * as THREE from 'three';

const LOGS_PER_PAGE = 8;
const LOGS_PER_SPREAD = LOGS_PER_PAGE * 2;

function LogPage({ logs, isLeft }) {
  return (
    <div style={{
      width: '840px', 
      height: '1140px',
      padding: '40px 60px',
      color: '#fff',
      fontFamily: '"Fira Code", monospace',
      fontSize: '42px',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      gap: '24px',
      background: 'rgba(0, 15, 30, 0.6)',
      border: '4px solid rgba(6, 182, 212, 0.4)',
      boxShadow: 'inset 0 0 40px rgba(6, 182, 212, 0.3)',
      borderRadius: '16px',
      backdropFilter: 'blur(8px)'
    }}>
      <h3 style={{ margin: 0, color: '#06b6d4', borderBottom: '3px solid rgba(6,182,212,0.4)', paddingBottom: '15px', fontSize: '50px' }}>
        {isLeft ? 'System.Log_A' : 'System.Log_B'}
      </h3>
      {logs.length === 0 && <span style={{ opacity: 0.5 }}>[Đang chờ dữ liệu...]</span>}
      {logs.map((log, i) => {
        const isErr = log.msg.includes('Lỗi');
        const isDone = log.msg.includes('Hoàn thành');
        const color = isErr ? '#f43f5e' : isDone ? '#8b5cf6' : '#22d3ee';
        return (
          <div key={i} style={{ display: 'flex', gap: '16px', borderBottom: '2px dashed rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
            <span style={{ opacity: 0.5, flexShrink: 0 }}>[{log.time}]</span>
            <span style={{ color, textShadow: `0 0 12px ${color}` }}>{log.msg}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function HoloBook({ logs = [], isRunning }) {
  const bookRef = useRef();
  const flipperRef = useRef();
  
  const [currentSpread, setCurrentSpread] = useState(0);
  const [isFlipping, setIsFlipping] = useState(false);
  const [flipDirection, setFlipDirection] = useState(1); // 1 = next, -1 = prev

  const totalSpreads = Math.max(1, Math.ceil(logs.length / LOGS_PER_SPREAD));

  useEffect(() => {
    if (totalSpreads - 1 > currentSpread) {
      handleFlip(1);
    }
  }, [totalSpreads]);

  const handleFlip = (dir) => {
    if (isFlipping) return;
    const nextSpread = currentSpread + dir;
    if (nextSpread >= 0 && nextSpread < totalSpreads) {
      setFlipDirection(dir);
      setIsFlipping(true);
      setTimeout(() => {
        setCurrentSpread(nextSpread);
        setIsFlipping(false);
      }, 600);
    }
  };

  useFrame((state, delta) => {
    if (bookRef.current) {
      bookRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.5) * 0.1;
      bookRef.current.position.y = Math.sin(state.clock.elapsedTime * 1) * 0.1;
    }

    if (flipperRef.current && isFlipping) {
      const targetRot = flipDirection === 1 ? Math.PI : 0;
      flipperRef.current.rotation.y = THREE.MathUtils.lerp(flipperRef.current.rotation.y, targetRot, delta * 8);
    } else if (flipperRef.current) {
      flipperRef.current.rotation.y = flipDirection === 1 ? 0 : Math.PI;
    }
  });

  const startIndex = currentSpread * LOGS_PER_SPREAD;
  const leftLogs = logs.slice(startIndex, startIndex + LOGS_PER_PAGE);
  const rightLogs = logs.slice(startIndex + LOGS_PER_PAGE, startIndex + LOGS_PER_SPREAD);

  const coverMat = useMemo(() => new THREE.MeshPhysicalMaterial({
    color: '#060611',
    metalness: 0.8,
    roughness: 0.2,
    clearcoat: 1.0,
    clearcoatRoughness: 0.1,
  }), []);

  const pageMat = useMemo(() => new THREE.MeshPhysicalMaterial({
    color: '#0a192f',
    emissive: '#06b6d4',
    emissiveIntensity: 0.2,
    metalness: 0.1,
    roughness: 0.5,
    transmission: 0.5,
    thickness: 0.5
  }), []);

  // Góc nghiêng tự nhiên của sách mở
  const bookAngle = 0.1;

  return (
    <group ref={bookRef} rotation={[0.15, 0, 0]} scale={[1.3, 1.3, 1.3]} position={[0, 0.2, 0]}>
      {/* Bìa trái */}
      <mesh position={[-1.5, 0, -0.1]} rotation={[0, bookAngle, 0]} material={coverMat}>
        <boxGeometry args={[3.1, 4.2, 0.1]} />
      </mesh>
      
      {/* Bìa phải */}
      <mesh position={[1.5, 0, -0.1]} rotation={[0, -bookAngle, 0]} material={coverMat}>
        <boxGeometry args={[3.1, 4.2, 0.1]} />
      </mesh>

      {/* Gáy sách bìa */}
      <mesh position={[0, 0, -0.15]} material={coverMat}>
        <boxGeometry args={[0.4, 4.2, 0.2]} />
      </mesh>
      
      {/* Gáy sách giấy (nếp gấp giữa) */}
      <mesh position={[0, 0, -0.02]} material={pageMat}>
        <boxGeometry args={[0.2, 3.9, 0.15]} />
      </mesh>

      {/* Khối giấy trái */}
      <mesh position={[-1.45, 0, 0.05]} rotation={[0, bookAngle, 0]} material={pageMat}>
        <boxGeometry args={[2.8, 3.9, 0.15]} />
        {/* Nội dung trang trái */}
        <Html transform position={[0, 0, 0.08]} scale={0.0033}>
          <LogPage logs={leftLogs} isLeft={true} />
        </Html>
      </mesh>

      {/* Khối giấy phải */}
      <mesh position={[1.45, 0, 0.05]} rotation={[0, -bookAngle, 0]} material={pageMat}>
        <boxGeometry args={[2.8, 3.9, 0.15]} />
        {/* Nội dung trang phải */}
        <Html transform position={[0, 0, 0.08]} scale={0.0033}>
          <LogPage logs={rightLogs} isLeft={false} />
        </Html>
      </mesh>

      {/* Trang đang lật (Hiệu ứng mỏng) */}
      {isFlipping && (
        <group position={[0, 0, 0.15]} ref={flipperRef}>
          <mesh position={[1.4, 0, 0]} material={pageMat}>
            <boxGeometry args={[2.8, 3.9, 0.02]} />
          </mesh>
        </group>
      )}

      {/* Bảng điều khiển HTML */}
      <Html transform position={[0, -2.6, 0.5]} scale={0.04}>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center', background: 'rgba(0,0,0,0.8)', padding: '10px 24px', borderRadius: '30px', border: '1px solid rgba(6, 182, 212, 0.5)', boxShadow: '0 0 20px rgba(6,182,212,0.3)', pointerEvents: 'auto' }}>
          <button 
            onClick={(e) => { e.stopPropagation(); handleFlip(-1); }}
            disabled={currentSpread === 0}
            style={{ background: 'transparent', color: currentSpread === 0 ? '#555' : '#06b6d4', border: 'none', cursor: 'pointer', fontSize: '28px', fontWeight: 'bold' }}
          >
            ←
          </button>
          <span style={{ color: '#fff', fontFamily: '"Fira Code", monospace', fontSize: '16px', letterSpacing: '1px' }}>
            PAGE {currentSpread + 1} / {totalSpreads}
          </span>
          <button 
            onClick={(e) => { e.stopPropagation(); handleFlip(1); }}
            disabled={currentSpread >= totalSpreads - 1}
            style={{ background: 'transparent', color: currentSpread >= totalSpreads - 1 ? '#555' : '#06b6d4', border: 'none', cursor: 'pointer', fontSize: '28px', fontWeight: 'bold' }}
          >
            →
          </button>
        </div>
      </Html>
    </group>
  );
}
