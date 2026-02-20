---
title: "EDFA Gain Spectrum Modeling with ML"
type: domain
tags: [edfa, gain-spectrum, noise-figure, ml, transfer-learning, optical-amplifier, jocn]
domain: optical-networking
created: 2026-02-20
updated: 2026-02-20
confidence: high
complexity: high
related: [transfer_learning_optical_models]
---

# EDFA Gain Spectrum Modeling with ML

## Problem

EDFAs (Erbium-Doped Fiber Amplifiers) are the backbone of long-haul optical networks, but their gain is not flat — it varies across the C-band spectrum and depends on input power, channel loading, pump power, and amplifier design. Accurate gain spectrum prediction is critical for network planning, digital twins, and autonomous operation. Physics-based models exist but require detailed amplifier parameters that operators often don't have. ML models can learn the input-output mapping from operational data.

## Context

This knowledge comes from modeling EDFA gain spectra and booster noise figures on the Open Ireland testbed at TCD, using ADTRAN FSP3000 equipment. The work involved JOCN publication, transfer learning between amplifier types, and integration with digital twin models.

Key constraints in real-world EDFA modeling:
- Limited training data (amplifiers can't be taken offline for exhaustive characterization)
- Gain depends on channel loading pattern (which channels are on/off), not just total power
- Amplifiers of the same model behave differently due to manufacturing variation and aging
- Need sub-0.5 dB accuracy for practical network planning

## Approach

### Input Representation
- **Per-channel input powers** across the C-band (typically 80-96 channels on 50 GHz grid)
- **Channel presence mask** (binary: which channels are lit)
- **Amplifier operating point** (total input power, gain setpoint or pump current)
- Optional: amplifier temperature, age metadata

### Output
- **Per-channel gain values** (dB) across the spectrum
- Or equivalently: per-channel output powers

### Model Architecture
Neural networks work well here. Key architectural choices:
- **Input layer**: concatenation of per-channel powers and channel mask
- **Hidden layers**: 2-4 fully connected layers, 128-512 neurons each
- **Output layer**: per-channel gain (same dimension as input spectrum)
- **Activation**: ReLU for hidden layers, linear for output
- **Loss**: MSE on per-channel gain, optionally weighted by channel presence

### Transfer Learning Strategy
The key insight: EDFAs share common physics (erbium emission/absorption cross-sections), so a model trained on one amplifier captures general EDFA behavior. Fine-tuning on a small dataset from a new amplifier is far more efficient than training from scratch.

1. **Pre-train** on a well-characterized source amplifier (extensive dataset)
2. **Freeze early layers** (which learn general spectral shape features)
3. **Fine-tune final layers** on the target amplifier with limited data (as few as 50-100 samples)
4. Achieves comparable accuracy to full training with 10-20x less target data

### Noise Figure Modeling
Noise figure (NF) follows similar principles but is harder:
- NF depends on population inversion, which is less directly observable
- ASE noise measurements are noisier than gain measurements
- Booster NF modeling requires careful handling of the gain-NF tradeoff

## Key Decisions

**Per-channel representation over summary statistics**: Using individual channel powers as input (instead of total power + tilt) captures the loading-dependent gain variation that matters most. The model sees the spectral hole burning effect directly.

**Transfer learning over per-amplifier training**: In a network with dozens of amplifiers, collecting exhaustive training data for each is impractical. Transfer learning makes the approach scalable.

**Neural network over Gaussian processes or linear models**: GPs give uncertainty estimates but don't scale well to 80+ dimensional input. Linear models miss the nonlinear gain competition effects. NNs hit the sweet spot of accuracy and scalability.

**MSE loss over spectral loss functions**: Tried custom losses (e.g., penalizing spectral tilt errors more), but plain MSE with per-channel outputs worked best. The model naturally learns spectral correlations.

## Pitfalls & Gotchas

**Channel loading is critical and often overlooked.** A model trained only on fully-loaded spectra will fail badly on partial loading. Always include varied channel loading patterns in training data — especially edge cases like single-channel and adjacent-channel scenarios.

**Gain setpoint vs. actual gain.** Operators set a target gain, but actual gain can differ due to control loop limitations, tilt compensation, etc. Use actual measured gain as the training target, not the setpoint.

**Amplifier aging changes behavior.** A model trained on a fresh amplifier will drift as the amplifier ages (pump degradation, fiber darkening). Plan for periodic retraining or online adaptation.

**Temperature sensitivity.** EDFA gain varies with temperature (~0.01-0.05 dB/C per channel depending on position). If the testbed has temperature fluctuations, include temperature as an input feature or normalize for it.

**Interpolation vs. extrapolation.** ML models interpolate well but extrapolate poorly. If the training data doesn't include high total input powers, the model will be unreliable there. Characterize the convex hull of your training data.

**NF measurement noise.** Noise figure measurements from OSA-based methods have ~0.3-0.5 dB uncertainty. This limits achievable NF model accuracy. Use averaged/filtered NF measurements for training.

## Recipe

1. **Collect training data** from the target amplifier:
   - Vary channel loading (full, partial with different patterns, single channel)
   - Vary input power levels across the operational range
   - Record: per-channel input power, per-channel output power, gain setpoint, pump current, temperature
   - Minimum: 200-500 configurations for direct training, 50-100 for transfer learning

2. **Preprocess**:
   - Compute per-channel gain: `G_ch = P_out_ch - P_in_ch` (in dB)
   - Create channel presence mask from input powers (threshold at noise floor)
   - Normalize input powers and gains to zero-mean, unit-variance per feature
   - Split: 70/15/15 train/val/test

3. **Build the model**:
   - Input: `[per_channel_powers (N_ch), channel_mask (N_ch), operating_point (1-3)]`
   - Architecture: FC layers `[2*N_ch+k] -> 256 -> 256 -> 128 -> [N_ch]`
   - Optimizer: Adam, lr=1e-3 with scheduler (reduce on plateau)
   - Train for 200-500 epochs, early stopping on validation loss

4. **For transfer learning**:
   - Load pre-trained weights from source amplifier model
   - Freeze all layers except the last 1-2 layers
   - Fine-tune on target data with lower learning rate (1e-4)
   - 50-100 epochs typically sufficient

5. **Evaluate**:
   - Per-channel MAE and max error across test set
   - Spectral error profile (which wavelengths have highest error?)
   - Performance vs. channel count (does accuracy degrade at low loading?)
   - Target: MAE < 0.3 dB, max error < 1.0 dB for practical use

## Verification

- Per-channel gain MAE < 0.3 dB on held-out test set
- Error doesn't systematically increase at band edges (common failure mode)
- Model generalizes across channel loading patterns not seen in training
- Transfer-learned model matches fully-trained model accuracy (within 0.1 dB MAE)
- Residual errors are spectrally uncorrelated (no systematic tilt or ripple bias)
