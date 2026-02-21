import { useEffect, useRef } from "react";
import { Animated, Easing } from "react-native";
import Svg, {
  Defs,
  LinearGradient,
  RadialGradient,
  Stop,
  G,
  Rect,
  Path,
  Circle,
} from "react-native-svg";

const AnimatedG = Animated.createAnimatedComponent(G);

interface SieveLogoProps {
  size?: number;
  animate?: boolean;
}

export default function SieveLogo({ size = 80, animate = false }: SieveLogoProps) {
  const siftAnim = useRef(new Animated.Value(0)).current;
  const particleAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!animate) return;

    const sift = Animated.loop(
      Animated.sequence([
        Animated.timing(siftAnim, { toValue: 1, duration: 2500, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(siftAnim, { toValue: 0, duration: 0, useNativeDriver: true }),
      ])
    );

    const particle = Animated.loop(
      Animated.sequence([
        Animated.timing(particleAnim, { toValue: 1, duration: 1800, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(particleAnim, { toValue: 0, duration: 1800, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])
    );

    sift.start();
    particle.start();

    return () => {
      sift.stop();
      particle.stop();
    };
  }, [animate, siftAnim, particleAnim]);

  const height = size * 0.4875;

  // Row 1 holes
  const row1 = [115, 149, 183, 217, 251, 285];
  // Row 2 holes
  const row2: [number, number][] = [[132, 95], [166, 102], [200, 106], [234, 102], [268, 95]];
  // Particles
  const particles: [number, number, number][] = [
    [140, 135, 4.4], [170, 139, 4.6], [200, 142, 4.9], [230, 139, 4.6],
    [260, 135, 4.4], [160, 159, 5.7], [200, 167, 6.4], [240, 159, 5.7],
  ];

  return (
    <Svg
      viewBox="0 0 400 195"
      width={size}
      height={height}
    >
      <Defs>
        <LinearGradient id="sw-goldBody" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0%" stopColor="#E8C84A" />
          <Stop offset="18%" stopColor="#D4A832" />
          <Stop offset="40%" stopColor="#C49528" />
          <Stop offset="65%" stopColor="#A87A1E" />
          <Stop offset="85%" stopColor="#8B6318" />
          <Stop offset="100%" stopColor="#6E4E12" />
        </LinearGradient>
        <LinearGradient id="sw-rimGold" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0%" stopColor="#F0D860" />
          <Stop offset="50%" stopColor="#C8A830" />
          <Stop offset="100%" stopColor="#A08020" />
        </LinearGradient>
        <LinearGradient id="sw-bodySheen" x1="0" y1="0" x2="1" y2="0">
          <Stop offset="0%" stopColor="rgba(255,255,255,0)" />
          <Stop offset="35%" stopColor="rgba(255,255,255,0.18)" />
          <Stop offset="50%" stopColor="rgba(255,255,255,0.22)" />
          <Stop offset="65%" stopColor="rgba(255,255,255,0.18)" />
          <Stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </LinearGradient>
        <RadialGradient id="sw-holeSage" cx="50%" cy="45%" r="50%">
          <Stop offset="0%" stopColor="#E8F3ED" />
          <Stop offset="40%" stopColor="#CEE3D8" />
          <Stop offset="70%" stopColor="#9DC7B1" />
          <Stop offset="100%" stopColor="#6B9E80" />
        </RadialGradient>
        <RadialGradient id="sw-particleGold" cx="40%" cy="35%" r="55%">
          <Stop offset="0%" stopColor="#F0D860" />
          <Stop offset="45%" stopColor="#D4A832" />
          <Stop offset="100%" stopColor="#8B6318" />
        </RadialGradient>
      </Defs>
      <G>
        {/* Rim */}
        <Rect x={42} y={28} width={316} height={16} rx={3} fill="url(#sw-rimGold)" />
        <Rect x={42} y={29} width={316} height={3} rx={1.5} fill="rgba(255,255,220,0.18)" />
        {/* Bowl */}
        <Path
          d="M48,42 L352,42 Q350,50 346,58 Q330,88 305,102 Q270,120 200,124 Q130,120 95,102 Q70,88 54,58 Q50,50 48,42 Z"
          fill="url(#sw-goldBody)"
        />
        <Path
          d="M48,42 L352,42 Q350,50 346,58 Q330,88 305,102 Q270,120 200,124 Q130,120 95,102 Q70,88 54,58 Q50,50 48,42 Z"
          fill="url(#sw-bodySheen)"
        />
        {/* Row 1 holes */}
        {row1.map((cx) => (
          <G key={cx}>
            <Circle cx={cx} cy={68} r={6.8} fill="url(#sw-holeSage)" />
            <Circle cx={cx - 2} cy={66} r={2.3} fill="rgba(255,255,255,0.45)" />
          </G>
        ))}
        {/* Row 2 holes */}
        {row2.map(([cx, cy]) => (
          <G key={cx}>
            <Circle cx={cx} cy={cy} r={6.4} fill="url(#sw-holeSage)" />
            <Circle cx={cx - 2} cy={cy - 2} r={2.1} fill="rgba(255,255,255,0.42)" />
          </G>
        ))}
        {/* Particles */}
        {particles.map(([cx, cy, r]) => (
          <Circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} fill="url(#sw-particleGold)" />
        ))}
      </G>
    </Svg>
  );
}
