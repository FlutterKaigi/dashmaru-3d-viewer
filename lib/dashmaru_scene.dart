import 'dart:math' as math;

import 'package:flutter_scene/scene.dart' as scene;
import 'package:vector_math/vector_math.dart' as vm;

import 'dashmaru_background.dart';
import 'sitting_playback.dart';
import 'motion_playback.dart';

/// The animations authored into the master glTF model.
enum DashmaruMotion {
  walk('Walk', '歩く', 'てくてく、いっしょに。'),
  jump('Jump', 'ジャンプ', '羽ばたいて、ふわっ。'),
  wave('Wave', '手を振る', 'またね、バイバイ！'),
  blink('Blink', 'まばたき', 'ぱちっ。ひとやすみ。'),
  idle('Idle', '待機', 'ゆらゆら、のんびり。'),
  run('Run', '走る', 'ぱたぱた、とてとて。'),
  shake('Shake', 'ぶんぶん', 'ぶんぶん、ぷるぷる。'),
  sit('Sit', '座る', 'ちょこんと、ひとやすみ。'),
  nod('Nod', 'うなずく', 'うんうん、なるほど。'),
  tilt('Tilt', '首かしげ', 'ん？ どういうことかな。'),
  bow('Bow', 'おじぎ', 'ぺこり、ありがとう。'),
  celebrate('Celebrate', 'よろこぶ', 'やった！ ぴょんぴょん！'),
  stretch('Stretch', 'のび', 'ぐーっと伸びて、ひと息。');

  const DashmaruMotion(this.clipName, this.label, this.caption);
  final String clipName;
  final String label;
  final String caption;

  static DashmaruMotion parse(String? value) => values.firstWhere(
    (motion) => motion.clipName.toLowerCase() == value?.toLowerCase(),
    orElse: () => idle,
  );
}

/// The user's preferred expression, restored after the jump's exertion face.
enum DashmaruExpression {
  normal('FaceNormal', '通常'),
  smile('FaceSmile', '笑顔'),
  spiral('FaceSpiral', 'ぐるぐる'),
  strain('FaceStrain', '踏ん張る');

  const DashmaruExpression(this.nodeName, this.label);
  final String nodeName;
  final String label;

  static DashmaruExpression parse(String? value) => values.firstWhere(
    (expression) => expression.name == value?.toLowerCase(),
    orElse: () => normal,
  );

  /// Jump overrides the preference only for its authored airborne phase.
  /// Use the clip's time, so seeking, pausing and playback speed stay in sync
  /// with the wings instead of running a separate expression timer.
  static DashmaruExpression forPlayback({
    required DashmaruMotion motion,
    required DashmaruExpression preferred,
    required double playbackTime,
    required double duration,
  }) {
    if (motion != DashmaruMotion.jump) return preferred;
    if (duration <= 0) return normal;
    return playbackTime >= duration * 0.23 && playbackTime < duration * 0.81
        ? strain
        : normal;
  }
}

/// Owns the retained Flutter Scene graph and its glTF animation clips.
///
/// glTF is Y-up / +Z-front. Flutter Scene converts the imported asset to its
/// left-handed coordinates, making -Z the front in the runtime scene.
class DashmaruScene {
  DashmaruScene({this.cameraTargetY = 1.5});

  final double cameraTargetY;
  late final scene.Scene sceneGraph = scene.Scene();
  final Map<DashmaruMotion, scene.AnimationClip> _clips = {};
  final Map<DashmaruMotion, double> durations = {};
  final Map<DashmaruExpression, scene.Node> _expressionNodes = {};
  scene.PhysicallyBasedMaterial? _plinthMaterial;
  MotionPlayback<DashmaruMotion>? _playback;

  DashmaruMotion get motion => _playback?.motion ?? DashmaruMotion.idle;
  DashmaruExpression expression = DashmaruExpression.normal;
  DashmaruBackground background = DashmaruBackground.mint;
  DashmaruExpression get displayedExpression => DashmaruExpression.forPlayback(
    motion: motion,
    preferred: expression,
    playbackTime: _playback?.playbackTime ?? 0,
    duration: durations[motion] ?? 0,
  );

  String get expressionDescription => motion == DashmaruMotion.jump
      ? '空中で羽ばたく間は踏ん張る表情、それ以外は通常の表情。'
      : '表情は${expression.label}。';
  bool get playing => _playback?.playing ?? true;
  bool orbiting = false;
  double get speed => _playback?.speed ?? 1;
  double yaw = 0;
  double elevation = 0.03;
  double distance = 12;

  Future<void> load({
    required DashmaruMotion initialMotion,
    DashmaruExpression initialExpression = DashmaruExpression.normal,
    DashmaruBackground initialBackground = DashmaruBackground.mint,
    double? initialTime,
    String? initialCamera,
    double? initialZoom,
  }) async {
    selectBackground(initialBackground);
    await scene.Scene.initializeStaticResources();
    final model = await scene.loadScene('assets/models/dashmaru.glb');
    sceneGraph.add(model);

    // Register every clip before playing so all share the authored bind pose.
    for (final motion in DashmaruMotion.values) {
      final animation = model.findAnimationByName(motion.clipName);
      if (animation == null) {
        throw StateError('3D モデルに ${motion.clipName} アニメーションがありません。');
      }
      _clips[motion] = model.createAnimationClip(animation)
        ..weight = 0
        ..loop = motion != DashmaruMotion.sit;
      durations[motion] = animation.endTime;
    }

    _playback = MotionPlayback(
      clips: _clips,
      sitting: DashmaruMotion.sit,
      sittingDuration: durations[DashmaruMotion.sit]!,
      motion: DashmaruMotion.idle,
      // Fixed gait phases minimize sole penetration while blending from bind.
      // All exported sole vertices: Walk >= -0.00324, Run >= -0.00497.
      gaitEntrances: const {
        DashmaruMotion.walk: 0.5775,
        DashmaruMotion.run: 0.057,
      },
    );

    for (final expression in DashmaruExpression.values) {
      final node = model.getChildByName(expression.nodeName);
      if (node == null) {
        throw StateError('3D モデルに ${expression.label} の表情がありません。');
      }
      // glTF has no visibility flag, so the alternate faces are authored at
      // tiny scales. Restore their size once, then hide their entire subtree.
      // None of these group transforms belongs to an animation track.
      _expressionNodes[expression] = node..scale = vm.Vector3.all(1);
    }
    selectExpression(initialExpression);

    // A broad studio reflection and asymmetric key reveal the rounded forms.
    // The palette stays in the model; light only describes its volume.
    sceneGraph.antiAliasingMode =
        scene.Scene.isAntiAliasingModeSupported(scene.AntiAliasingMode.msaa)
        ? scene.AntiAliasingMode.msaa
        : scene.AntiAliasingMode.smaa;
    sceneGraph.environmentSettings = scene.EnvironmentSettings(
      environment: scene.EnvironmentMap.studio(),
      toneMapping: scene.ToneMappingMode.pbrNeutral,
      exposure: 1.0,
      environmentIntensity: 0.90,
      ambientOcclusionEnabled: true,
      ambientOcclusionIntensity: 0.22,
      ambientOcclusionHalfResolution: false,
    );
    sceneGraph.directionalLight = scene.DirectionalLight(
      direction: vm.Vector3(0.4, -1, 0.5),
      intensity: 2.0,
      priority: 1,
      castsShadow: true,
      shadowCascadeCount: 1,
      shadowMaxDistance: 16,
      shadowMapResolution: 2048,
      shadowFilter: scene.DirectionalShadowFilter.rotatedPoisson,
      shadowSoftness: 0.14,
      shadowDepthBias: 0.003,
      shadowNormalBias: 0.008,
    );
    // A low front bounce keeps the white bib readable under the round belly.
    sceneGraph.add(
      scene.Node(name: 'Soft front bounce')..addComponent(
        scene.DirectionalLightComponent.aimed(
          scene.DirectionalLight(intensity: 0.85),
          vm.Vector3(0, 0.4, 1),
        ),
      ),
    );

    // A soft rear bounce keeps the cyan readable when inspecting the tail.
    sceneGraph.add(
      scene.Node(name: 'Soft rear bounce')..addComponent(
        scene.DirectionalLightComponent.aimed(
          scene.DirectionalLight(intensity: 0.35),
          vm.Vector3(0.25, 0.25, -1),
        ),
      ),
    );

    _plinthMaterial = scene.PhysicallyBasedMaterial()
      ..metallicFactor = 0
      ..roughnessFactor = 0.92;
    selectBackground(background);
    final plinth = scene.Node(
      name: 'Display plinth',
      mesh: scene.Mesh(
        scene.CylinderGeometry(
          topRadius: 1.65,
          bottomRadius: 1.65,
          height: 0.085,
          radialSegments: 96,
        ),
        _plinthMaterial!,
      ),
    )..position = vm.Vector3(0, -0.085 / 2, 0);
    sceneGraph.add(plinth);
    setCamera(initialCamera ?? 'front');
    if (initialZoom != null && initialZoom.isFinite && initialZoom > 0) {
      distance = (12 / initialZoom).clamp(4.5, 16);
    }
    selectMotion(initialMotion, animateTransition: false);
    if (initialTime != null) {
      _clips[motion]!.seek(
        motion == DashmaruMotion.sit
            ? SittingPlayback.position(initialTime, durations[motion]!)
            : initialTime,
      );
      setPlaying(false);
      sceneGraph.update(0);
      _updateExpressionVisibility();
    }
  }

  void selectMotion(DashmaruMotion value, {bool animateTransition = true}) {
    _playback!.selectMotion(value, animateTransition: animateTransition);
    _updateExpressionVisibility();
  }

  void setPlaying(bool value) => _playback!.setPlaying(value);

  void selectExpression(DashmaruExpression value) {
    expression = value;
    _updateExpressionVisibility();
  }

  void selectBackground(DashmaruBackground value) {
    background = value;
    final (red, green, blue) = value.plinthColor;
    _plinthMaterial?.baseColorFactor = vm.Vector4(red, green, blue, 1);
  }

  void _updateExpressionVisibility() {
    final displayed = displayedExpression;
    for (final entry in _expressionNodes.entries) {
      entry.value.visible = entry.key == displayed;
    }
  }

  void setSpeed(double value) => _playback!.setSpeed(value);

  void setCamera(String preset) {
    orbiting = false;
    elevation = 0.03;
    yaw = switch (preset) {
      'side' => math.pi / 2,
      'back' => math.pi,
      'three-quarter' => -math.pi / 5,
      _ => 0,
    };
  }

  void reset() {
    distance = 12;
    setCamera('front');
    setSpeed(1);
    selectExpression(DashmaruExpression.normal);
    selectBackground(DashmaruBackground.mint);
    selectMotion(DashmaruMotion.idle, animateTransition: false);
  }

  void drag(double dx, double dy) {
    orbiting = false;
    yaw -= dx * 0.009;
    elevation = (elevation + dy * 0.004).clamp(-0.08, 0.65);
  }

  void zoom(double scrollDelta) {
    distance = (distance + scrollDelta * 0.012).clamp(4.5, 16);
  }

  void tick(Duration elapsed, double deltaSeconds) {
    final delta = math.min(deltaSeconds, 0.05);
    if (orbiting) yaw += delta * 0.35;
    // Advance each real clip once, then apply its already sampled pose.
    _playback!.advance(delta);
    sceneGraph.update(0);
    _updateExpressionVisibility();
  }

  scene.PerspectiveCamera camera(Duration elapsed) => scene.PerspectiveCamera(
    position: vm.Vector3(
      math.sin(yaw) * distance,
      cameraTargetY + math.tan(elevation) * distance,
      -math.cos(yaw) * distance,
    ),
    target: vm.Vector3(0, cameraTargetY, 0),
    fovRadiansY: 22 * math.pi / 180,
    fovNear: 0.1,
    fovFar: 30,
  );
}
