/**
 * Personal PC Assistant - Premium Sci-Fi / Cyberpunk Control Panel
 * React + Tailwind CSS + Framer Motion
 * 
 * Features:
 * - Fade-in + bloom/glow animations on startup
 * - Deep black gradient background with animated noise/grain
 * - Neon orange accents with glow effects
 * - Glassmorphism panels with pulsing borders
 * - Animated waveform audio monitor
 * - Sequential reveal animations
 * - Subtle scanline/matrix rain background
 */

import React, { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Types
interface Config {
  hotkey: string;
  micDevice: string | null;
  ollamaModel: string;
  appAliases: Record<string, string>;
}

interface Status {
  assistant: 'READY' | 'LOADING' | 'ERROR';
  hotkey: 'CONFIGURED' | 'NOT_CONFIGURED';
  microphone: 'ACTIVE' | 'INACTIVE' | 'CHECKING';
  ollama: 'RUNNING' | 'INSTALLED' | 'NOT_FOUND' | 'CHECKING';
}

// Main Component
export const MainControlPanel: React.FC = () => {
  const [config, setConfig] = useState<Config>({
    hotkey: 'right shift',
    micDevice: null,
    ollamaModel: 'gemma3:12b',
    appAliases: {},
  });

  const [status, setStatus] = useState<Status>({
    assistant: 'READY',
    hotkey: 'CONFIGURED',
    microphone: 'CHECKING',
    ollama: 'CHECKING',
  });

  const [isLoaded, setIsLoaded] = useState(false);
  const [waveformData, setWaveformData] = useState<number[]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Startup animation sequence
  useEffect(() => {
    const timer = setTimeout(() => setIsLoaded(true), 100);
    return () => clearTimeout(timer);
  }, []);

  // Waveform animation
  useEffect(() => {
    const interval = setInterval(() => {
      // Simulate audio data (replace with real mic input)
      const newData = Array.from({ length: 100 }, () => Math.random() * 60 + 20);
      setWaveformData(newData);
    }, 50);

    return () => clearInterval(interval);
  }, []);

  // Draw waveform on canvas
  useEffect(() => {
    if (!canvasRef.current || waveformData.length === 0) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, width, height);

    // Draw waveform with gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, '#ff6600');
    gradient.addColorStop(0.5, '#ff9900');
    gradient.addColorStop(1, 'transparent');

    ctx.strokeStyle = gradient;
    ctx.lineWidth = 3;
    ctx.beginPath();

    const step = width / waveformData.length;
    waveformData.forEach((value, index) => {
      const x = index * step;
      const y = height - (value / 100) * height;
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.stroke();

    // Add glow effect
    ctx.shadowBlur = 15;
    ctx.shadowColor = '#ff6600';
    ctx.stroke();
  }, [waveformData]);

  return (
    <div className="relative w-full h-screen overflow-hidden bg-black">
      {/* Animated Background Gradient */}
      <div className="absolute inset-0 bg-gradient-radial from-black via-black to-[#0f0f1a] opacity-100" />

      {/* Subtle Noise/Grain Overlay */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='4' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
          animation: 'grain 8s steps(10) infinite',
        }}
      />

      {/* Subtle Scanline Effect */}
      <div
        className="absolute inset-0 opacity-[0.05] pointer-events-none"
        style={{
          background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255, 102, 0, 0.1) 2px, rgba(255, 102, 0, 0.1) 4px)',
          animation: 'scanline 8s linear infinite',
        }}
      />

      {/* Main Container */}
      <div className="relative z-10 w-full h-full flex flex-col">
        {/* Header - Sequential Reveal */}
        <motion.header
          initial={{ opacity: 0, y: -20 }}
          animate={isLoaded ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="relative px-6 py-4 border-b-2 border-[#ff6600] bg-black/50 backdrop-blur-sm"
        >
          <div className="flex items-center justify-between">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={isLoaded ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="text-[#ff6600] font-mono text-xs font-bold tracking-wider"
            >
              OBJECT IDENTIFICATION .. 01
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, scale: 0.9 }}
              animate={isLoaded ? { opacity: 1, scale: 1 } : {}}
              transition={{ duration: 1, delay: 0.4, ease: 'easeOut' }}
              className="text-white font-['Orbitron'] text-2xl font-bold tracking-widest text-center flex-1"
              style={{
                textShadow: '0 0 20px rgba(255, 102, 0, 0.8), 0 0 40px rgba(255, 102, 0, 0.4)',
                filter: isLoaded ? 'blur(0px)' : 'blur(2px)',
              }}
            >
              PERSONAL PC ASSISTANT
            </motion.h1>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={isLoaded ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="text-[#00ff00] font-mono text-xs font-bold tracking-wider"
            >
              STAT: READY
            </motion.div>
          </div>
        </motion.header>

        {/* Main Content - Three Columns */}
        <div className="flex-1 flex gap-4 p-4">
          {/* Left Panel - Configuration */}
          <motion.div
            initial={{ opacity: 0, x: -50 }}
            animate={isLoaded ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="flex-1 glass-panel"
          >
            <PanelTitle title="CONFIGURATION" />
            <div className="p-4 space-y-4">
              <ConfigField
                label="HOTKEY"
                value={config.hotkey}
                onChange={(val) => setConfig({ ...config, hotkey: val })}
              />
              <ConfigField
                label="MICROPHONE ID"
                value={config.micDevice || ''}
                onChange={(val) => setConfig({ ...config, micDevice: val || null })}
              />
              <ConfigField
                label="OLLAMA MODEL"
                value={config.ollamaModel}
                onChange={(val) => setConfig({ ...config, ollamaModel: val })}
              />
              <div>
                <label className="block text-[#ff6600] font-mono text-xs font-bold mb-2">
                  APP ALIASES (JSON)
                </label>
                <textarea
                  value={JSON.stringify(config.appAliases, null, 2)}
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value);
                      setConfig({ ...config, appAliases: parsed });
                    } catch {}
                  }}
                  className="w-full h-32 bg-black/70 border border-[#ff6600]/50 rounded p-2 text-white font-mono text-xs focus:border-[#ff6600] focus:ring-2 focus:ring-[#ff6600]/50 focus:outline-none transition-all"
                />
              </div>
            </div>
          </motion.div>

          {/* Center Panel - System Status */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={isLoaded ? { opacity: 1, scale: 1 } : {}}
            transition={{ duration: 0.8, delay: 0.8 }}
            className="flex-1 glass-panel"
          >
            <PanelTitle title="SYSTEM STATUS" />
            <div className="p-4 space-y-6">
              <StatusIndicators status={status} />
              <div>
                <label className="block text-[#ff6600] font-mono text-xs font-bold mb-2">
                  AUDIO MONITOR
                </label>
                <div className="relative bg-black/70 border border-[#ff6600]/50 rounded p-2 h-24">
                  <canvas
                    ref={canvasRef}
                    width={400}
                    height={80}
                    className="w-full h-full"
                  />
                </div>
              </div>
            </div>
          </motion.div>

          {/* Right Panel - Notices & Actions */}
          <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={isLoaded ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.8, delay: 1.0 }}
            className="flex-1 glass-panel"
          >
            <PanelTitle title="NOTICES & ACTIONS" />
            <div className="p-4 space-y-4">
              <WarningNotice />
              <ActionButtons
                onCheckOllama={() => {}}
                onSystemCheck={() => {}}
                onOpenConfig={() => {}}
                onSave={() => {}}
                onLaunch={() => {}}
              />
            </div>
          </motion.div>
        </div>

        {/* Footer - Status Bar */}
        <motion.footer
          initial={{ opacity: 0, y: 20 }}
          animate={isLoaded ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, delay: 1.2 }}
          className="px-6 py-3 border-t-2 border-[#ff6600] bg-black/50 backdrop-blur-sm"
        >
          <div className="flex items-center justify-between">
            <div className="flex gap-8">
              <StatusItem label="STATUS" value="OPERATIONAL" />
              <StatusItem label="MODE" value="CONFIGURATION" />
              <StatusItem label="VERSION" value="1.0.0" />
            </div>
            <div className="text-[#ff6600] font-mono text-xs font-bold">
              MESSAGE: [READY]
            </div>
          </div>
        </motion.footer>
      </div>

      {/* CSS Animations */}
      <style jsx>{`
        @keyframes grain {
          0%, 100% { transform: translate(0, 0); }
          10% { transform: translate(-5%, -5%); }
          20% { transform: translate(-10%, 5%); }
          30% { transform: translate(5%, -10%); }
          40% { transform: translate(-5%, 15%); }
          50% { transform: translate(-10%, 5%); }
          60% { transform: translate(15%, 0); }
          70% { transform: translate(0, 10%); }
          80% { transform: translate(-15%, 0); }
          90% { transform: translate(10%, 5%); }
        }

        @keyframes scanline {
          0% { transform: translateY(0); }
          100% { transform: translateY(100vh); }
        }

        .glass-panel {
          background: rgba(10, 10, 10, 0.4);
          backdrop-filter: blur(10px);
          border: 1px solid rgba(255, 102, 0, 0.3);
          border-radius: 8px;
          box-shadow: 0 0 20px rgba(255, 102, 0, 0.1);
          animation: pulse-border 3s ease-in-out infinite;
        }

        @keyframes pulse-border {
          0%, 100% { border-color: rgba(255, 102, 0, 0.3); }
          50% { border-color: rgba(255, 102, 0, 0.6); }
        }

        .bg-gradient-radial {
          background: radial-gradient(circle at center, #000000 0%, #0f0f1a 100%);
        }
      `}</style>
    </div>
  );
};

// Sub-components
const PanelTitle: React.FC<{ title: string }> = ({ title }) => (
  <div className="px-4 py-2 border-b border-[#ff6600]/30">
    <h2 className="text-[#ff6600] font-['Orbitron'] text-sm font-bold tracking-wider">
      {title}
    </h2>
  </div>
);

const ConfigField: React.FC<{
  label: string;
  value: string;
  onChange: (value: string) => void;
}> = ({ label, value, onChange }) => (
  <div>
    <label className="block text-[#ff6600] font-mono text-xs font-bold mb-2">
      {label}
    </label>
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-black/70 border border-[#ff6600]/50 rounded p-2 text-white font-mono text-xs focus:border-[#ff6600] focus:ring-2 focus:ring-[#ff6600]/50 focus:outline-none transition-all hover:border-[#ff6600]/70"
    />
  </div>
);

const StatusIndicators: React.FC<{ status: Status }> = ({ status }) => {
  const items = [
    { label: 'ASSISTANT', value: status.assistant, color: '#00ff00' },
    { label: 'HOTKEY', value: status.hotkey, color: '#00ff00' },
    { label: 'MICROPHONE', value: status.microphone, color: status.microphone === 'ACTIVE' ? '#00ff00' : '#ff6600' },
    { label: 'OLLAMA', value: status.ollama, color: status.ollama === 'RUNNING' ? '#00ff00' : '#ff6600' },
  ];

  return (
    <div className="space-y-3">
      {items.map((item, index) => (
        <motion.div
          key={item.label}
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 1.4 + index * 0.1 }}
          className="flex justify-between items-center"
        >
          <span className="text-[#ff6600] font-mono text-xs font-bold">
            {item.label}:
          </span>
          <span
            className="font-mono text-xs font-bold"
            style={{ color: item.color }}
          >
            {item.value}
          </span>
        </motion.div>
      ))}
    </div>
  );
};

const WarningNotice: React.FC = () => (
  <motion.div
    initial={{ opacity: 0, scale: 0.9 }}
    animate={{ opacity: 1, scale: 1 }}
    transition={{ delay: 1.6 }}
    className="bg-[#ff6600]/10 border-2 border-[#ff6600] rounded p-3"
    style={{
      boxShadow: '0 0 20px rgba(255, 102, 0, 0.3)',
    }}
  >
    <div className="flex items-center gap-2 mb-2">
      <span className="text-[#ff6600] text-xl">⚠</span>
      <span className="text-[#ff6600] font-['Orbitron'] text-sm font-bold">
        WARNING
      </span>
    </div>
    <p className="text-white/90 font-mono text-xs">
      Ensure admin rights for hotkey functionality
    </p>
  </motion.div>
);

const ActionButtons: React.FC<{
  onCheckOllama: () => void;
  onSystemCheck: () => void;
  onOpenConfig: () => void;
  onSave: () => void;
  onLaunch: () => void;
}> = ({ onCheckOllama, onSystemCheck, onOpenConfig, onSave, onLaunch }) => {
  const buttons = [
    { label: 'CHECK OLLAMA', onClick: onCheckOllama },
    { label: 'SYSTEM CHECK', onClick: onSystemCheck },
    { label: 'OPEN CONFIG', onClick: onOpenConfig },
    { label: 'SAVE CONFIG', onClick: onSave },
    { label: 'LAUNCH ASSISTANT', onClick: onLaunch, primary: true },
  ];

  return (
    <div className="space-y-2">
      {buttons.map((btn, index) => (
        <NeonButton
          key={btn.label}
          label={btn.label}
          onClick={btn.onClick}
          primary={btn.primary}
          delay={1.8 + index * 0.1}
        />
      ))}
    </div>
  );
};

const NeonButton: React.FC<{
  label: string;
  onClick: () => void;
  primary?: boolean;
  delay?: number;
}> = ({ label, onClick, primary = false, delay = 0 }) => (
  <motion.button
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay }}
    whileHover={{ scale: 1.03 }}
    whileTap={{ scale: 0.97 }}
    onClick={onClick}
    className={`
      w-full py-3 px-4 font-mono text-xs font-bold
      border-2 rounded
      transition-all duration-300
      relative overflow-hidden
      ${primary
        ? 'bg-[#ff6600]/20 border-[#ff6600] text-[#ff6600]'
        : 'bg-transparent border-[#ff6600]/50 text-[#ff6600] hover:border-[#ff6600]'
      }
    `}
    style={{
      boxShadow: primary
        ? '0 0 20px rgba(255, 102, 0, 0.5)'
        : '0 0 10px rgba(255, 102, 0, 0.2)',
    }}
  >
    <motion.span
      className="relative z-10"
      whileHover={{ textShadow: '0 0 10px rgba(255, 102, 0, 0.8)' }}
    >
      {label}
    </motion.span>
    <motion.div
      className="absolute inset-0 bg-[#ff6600]/20"
      initial={{ x: '-100%' }}
      whileHover={{ x: 0 }}
      transition={{ duration: 0.3 }}
    />
  </motion.button>
);

const StatusItem: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div>
    <div className="text-[#ff6600] font-mono text-[10px] font-bold">{label}</div>
    <div className="text-white font-mono text-xs font-bold">{value}</div>
  </div>
);

export default MainControlPanel;
