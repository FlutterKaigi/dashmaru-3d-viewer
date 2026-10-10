import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dashmaru_3d_viewer/dashmaru_background.dart';
import 'package:dashmaru_3d_viewer/dashmaru_scene.dart';
import 'package:dashmaru_3d_viewer/main.dart';

class _LoadingScene extends DashmaruScene {
  @override
  DashmaruMotion motion = DashmaruMotion.idle;
  @override
  bool playing = true;
  @override
  double speed = 1;

  @override
  Future<void> load({
    required DashmaruMotion initialMotion,
    DashmaruExpression initialExpression = DashmaruExpression.normal,
    DashmaruBackground initialBackground = DashmaruBackground.mint,
    double? initialTime,
    String? initialCamera,
    double? initialZoom,
  }) => Completer<void>().future;
}

void main() {
  for (final size in [
    const Size(320, 568),
    const Size(320, 640),
    const Size(390, 844),
    const Size(640, 360),
    const Size(800, 600),
    const Size(880, 720),
    const Size(1280, 720),
  ]) {
    for (final motion in [
      DashmaruMotion.idle,
      DashmaruMotion.jump,
      DashmaruMotion.sit,
      DashmaruMotion.bow,
    ]) {
      testWidgets(
        'viewer controls fit ${size.width} × ${size.height}: ${motion.name}',
        (tester) async {
          tester.view
            ..devicePixelRatio = 1
            ..physicalSize = size;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);

          // The loading shell has the same controls and stage constraints as the
          // ready viewer, without requiring a GPU in the widget-test process.
          final world = _LoadingScene()
            ..motion = motion
            ..expression = DashmaruExpression.smile
            ..speed = 0.5
            ..playing = false
            ..yaw = 0.8;
          await tester.pumpWidget(DashmaruApp(world: world));
          expect(tester.takeException(), isNull);
          for (final label in [
            '歩く',
            'ジャンプ',
            '手を振る',
            'まばたき',
            '待機',
            '走る',
            'ぶんぶん',
            '座る',
            'うなずく',
            '首かしげ',
            'おじぎ',
            'よろこぶ',
            'のび',
          ]) {
            expect(find.text(label), findsOneWidget);
          }
          final shortcuts = tester.widget<CallbackShortcuts>(
            find.byType(CallbackShortcuts),
          );
          expect(shortcuts.bindings, hasLength(15));
          final shortcutKeys = shortcuts.bindings.keys
              .whereType<SingleActivator>()
              .map((shortcut) => shortcut.trigger);
          expect(shortcutKeys, contains(LogicalKeyboardKey.keyT));
          expect(shortcutKeys, isNot(contains(LogicalKeyboardKey.keyE)));
          expect(find.text('きょろきょろ'), findsNothing);
          expect(find.text('010'), findsNothing);
          expect(find.text('キー 14'), findsNothing);
          expect(find.byType(ChoiceChip), findsNWidgets(8));
          for (final label in ['通常', '笑顔', 'ぐるぐる', '踏ん張る']) {
            expect(find.text(label), findsOneWidget);
          }
          expect(find.text('真顔'), findsNothing);
          expect(
            find.text('ジャンプは空中で羽ばたく間だけ踏ん張る表情'),
            motion == DashmaruMotion.jump ? findsOneWidget : findsNothing,
          );
          for (final label in ['ミント', 'スタジオ', 'ピーチ', '夜']) {
            expect(find.text(label), findsOneWidget);
          }
          // The last control must remain reachable on short/narrow displays.
          // Switching the backdrop also works during model loading and never
          // changes the character's current playback or camera settings.
          final night = find.widgetWithText(ChoiceChip, '夜');
          await tester.ensureVisible(night);
          await tester.tap(night);
          await tester.pump();
          expect(tester.takeException(), isNull);
          expect(world.background, DashmaruBackground.night);
          expect(tester.widget<ChoiceChip>(night).selected, isTrue);
          expect(world.motion, motion);
          expect(world.expression, DashmaruExpression.smile);
          expect(world.speed, 0.5);
          expect(world.playing, isFalse);
          expect(world.yaw, 0.8);
          await tester.pumpWidget(const SizedBox());
        },
      );
    }
  }
}
