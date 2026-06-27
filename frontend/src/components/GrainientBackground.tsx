import Grainient from "./Grainient";

const GrainientBackground = () => (
  <div aria-hidden="true" className="grainient-background">
    <div className="grainient-stage">
      <Grainient
        color1="#000000"
        color2="#164529"
        color3="#d7c796"
        timeSpeed={0.7}
        colorBalance={-0.49}
        warpStrength={1.8}
        warpFrequency={2.6}
        warpSpeed={1}
        warpAmplitude={50}
        blendAngle={72}
        blendSoftness={0.25}
        rotationAmount={760}
        noiseScale={0.7}
        grainAmount={0.1}
        grainScale={4.9}
        grainAnimated={false}
        contrast={1.2}
        gamma={0.9}
        saturation={0.5}
        centerX={-0.65}
        centerY={-0.29}
        zoom={1.2}
      />
    </div>
    <div className="grainient-shade" />
  </div>
);

export default GrainientBackground;
