import React from 'react';

export default function AnimatedBackground() {
  return (
    <div className="bg-container">
      {/* Lưới không gian 2D cuộn */}
      <div className="bg-grid"></div>
      
      {/* Các khối màu glowing di chuyển mượt mà */}
      <div className="bg-orb orb-primary"></div>
      <div className="bg-orb orb-accent"></div>
      <div className="bg-orb orb-danger"></div>
      
      {/* Hiệu ứng nhiễu/scanline nhẹ */}
      <div className="bg-scanlines"></div>
      
      {/* Bụi li ti bay */}
      <div className="particles">
        {Array.from({ length: 20 }).map((_, i) => (
          <div key={i} className="particle-2d" style={{
            left: `${Math.random() * 100}%`,
            animationDelay: `${Math.random() * 5}s`,
            animationDuration: `${10 + Math.random() * 15}s`
          }}></div>
        ))}
      </div>
    </div>
  );
}
