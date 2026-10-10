import 'dart:math' as math;

import 'package:flutter_test/flutter_test.dart';
import 'package:dashmaru_3d_viewer/dashmaru_background.dart';
import 'package:dashmaru_3d_viewer/dashmaru_scene.dart';

class _SceneWithoutClips extends DashmaruScene {
  @override
  DashmaruMotion motion = DashmaruMotion.idle;
  @override
  bool playing = true;
  @override
  double speed = 1;

  @override
  void setSpeed(double value) => speed = value;

  @override
  void selectMotion(DashmaruMotion value, {bool animateTransition = true}) {
    motion = value;
    playing = true;
  }
}

void main() {
  test('background URLs are stable and unknown values use mint', () {
    for (final background in DashmaruBackground.values) {
      final query = Uri.parse(
        'https://example.test/?background=${background.name}',
      ).queryParameters;
      expect(DashmaruBackground.parse(query['background']), background);
      expect(
        DashmaruBackground.parse(background.name.toUpperCase()),
        background,
      );
    }
    expect(DashmaruBackground.parse(null), DashmaruBackground.mint);
    expect(DashmaruBackground.parse('unknown'), DashmaruBackground.mint);
    expect(DashmaruMotion.parse('sit'), DashmaruMotion.sit);
  });

  test('removed motion URLs fall back to idle', () {
    for (final value in ['lookaround', 'LookAround', 'LOOKAROUND']) {
      final query = Uri.parse('https://example.test/?motion=$value')
          .queryParameters;
      expect(DashmaruMotion.parse(query['motion']), DashmaruMotion.idle);
    }
  });

  test('stage labels remain legible against every background', () {
    for (final background in DashmaruBackground.values) {
      for (final foreground in [background.inkColor, background.mutedColor]) {
        for (final backdrop in [background.centerColor, background.edgeColor]) {
          final a = foreground.computeLuminance();
          final b = backdrop.computeLuminance();
          final contrast = (math.max(a, b) + 0.05) / (math.min(a, b) + 0.05);
          expect(contrast, greaterThanOrEqualTo(4.5), reason: background.name);
        }
      }
    }
  });

  test('the overall reset restores the default background and pose', () {
    final world = _SceneWithoutClips()
      ..selectBackground(DashmaruBackground.night)
      ..motion = DashmaruMotion.sit
      ..expression = DashmaruExpression.smile
      ..distance = 6
      ..setSpeed(1.5);

    world.reset();

    expect(world.background, DashmaruBackground.mint);
    expect(world.motion, DashmaruMotion.idle);
    expect(world.expression, DashmaruExpression.normal);
    expect(world.distance, 12);
    expect(world.speed, 1);
  });
}
