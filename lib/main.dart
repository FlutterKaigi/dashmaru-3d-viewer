import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_scene/scene.dart' as scene;

import 'dashmaru_background.dart';
import 'dashmaru_scene.dart';

const _ink = Color(0xFF183E36);
const _green = Color(0xFF287757);
const _muted = Color(0xFF698179);
const _line = Color(0xFFE0E9E1);

const _motionShortcuts = [
  (LogicalKeyboardKey.digit1, '1'),
  (LogicalKeyboardKey.digit2, '2'),
  (LogicalKeyboardKey.digit3, '3'),
  (LogicalKeyboardKey.digit4, '4'),
  (LogicalKeyboardKey.digit5, '5'),
  (LogicalKeyboardKey.digit6, '6'),
  (LogicalKeyboardKey.digit7, '7'),
  (LogicalKeyboardKey.digit8, '8'),
  (LogicalKeyboardKey.digit9, '9'),
  (LogicalKeyboardKey.digit0, '0'),
  (LogicalKeyboardKey.keyQ, 'Q'),
  (LogicalKeyboardKey.keyW, 'W'),
  (LogicalKeyboardKey.keyT, 'T'),
];

int _motionColumns(double width) => width < 480
    ? 3
    : width < 720
    ? 4
    : 7;

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  LicenseRegistry.addLicense(() async* {
    yield LicenseEntryWithLineBreaks([
      'だしゅまる 3D ビューア / MIT',
    ], await rootBundle.loadString('LICENSE'));
    yield LicenseEntryWithLineBreaks(
      ['だしゅまる 3Dモデル / CC BY-NC-ND 4.0'],
      '${await rootBundle.loadString('assets/models/NOTICE.md')}\n\n'
      '${await rootBundle.loadString('assets/models/LICENSE')}',
    );
  });
  runApp(const DashmaruApp());
}

class DashmaruApp extends StatelessWidget {
  const DashmaruApp({super.key, this.world});

  final DashmaruScene? world;

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'だしゅまる 3D | FlutterKaigi',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: const Color(0xFFF8F9F3),
      colorScheme: ColorScheme.fromSeed(
        seedColor: _green,
        surface: const Color(0xFFF8F9F3),
      ),
      fontFamily: 'sans-serif',
      textTheme: const TextTheme(
        bodyMedium: TextStyle(color: _ink),
        bodyLarge: TextStyle(color: _ink),
      ),
    ),
    home: DashmaruViewer(world: world),
  );
}

class DashmaruViewer extends StatefulWidget {
  const DashmaruViewer({super.key, this.world});

  final DashmaruScene? world;

  @override
  State<DashmaruViewer> createState() => _DashmaruViewerState();
}

class _DashmaruViewerState extends State<DashmaruViewer> {
  // Leave room above the full-height celebration hops at the standard zoom.
  late final _world = widget.world ?? DashmaruScene(cameraTargetY: 1.8);
  bool _ready = false;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final query = Uri.base.queryParameters;
    try {
      await _world.load(
        initialMotion: DashmaruMotion.parse(query['motion']),
        initialExpression: DashmaruExpression.parse(query['expression']),
        initialBackground: DashmaruBackground.parse(query['background']),
        initialTime: double.tryParse(query['time'] ?? ''),
        initialCamera: query['camera'],
        initialZoom: double.tryParse(query['zoom'] ?? ''),
      );
      if (mounted) setState(() => _ready = true);
    } catch (error, stack) {
      debugPrint('Dashmaru model loading failed: $error\n$stack');
      if (mounted) setState(() => _error = error);
    }
  }

  void _selectMotion(DashmaruMotion motion) {
    if (_ready) setState(() => _world.selectMotion(motion));
  }

  void _selectExpression(DashmaruExpression expression) {
    if (_ready) setState(() => _world.selectExpression(expression));
  }

  void _selectBackground(DashmaruBackground background) {
    setState(() => _world.selectBackground(background));
  }

  void _togglePlay() {
    if (_ready) setState(() => _world.setPlaying(!_world.playing));
  }

  void _reset() {
    if (_ready) setState(_world.reset);
  }

  @override
  Widget build(BuildContext context) => CallbackShortcuts(
    bindings: {
      for (final motion in DashmaruMotion.values)
        SingleActivator(_motionShortcuts[motion.index].$1): () =>
            _selectMotion(motion),
      const SingleActivator(LogicalKeyboardKey.space): _togglePlay,
      const SingleActivator(LogicalKeyboardKey.keyR): _reset,
    },
    child: Focus(
      autofocus: true,
      child: Scaffold(
        body: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 760;
              final tight = constraints.maxHeight < 700;
              final content = Padding(
                padding: EdgeInsets.fromLTRB(
                  compact ? 20 : 40,
                  tight ? 18 : 28,
                  compact ? 20 : 40,
                  18,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _header(compact, tight),
                    SizedBox(height: tight ? 16 : 24),
                    Expanded(child: _stage(compact)),
                    const SizedBox(height: 18),
                    _motionControls(compact),
                    const SizedBox(height: 10),
                    _expressionControls(),
                    const SizedBox(height: 8),
                    _backgroundControls(),
                    const SizedBox(height: 8),
                    _footer(compact),
                  ],
                ),
              );
              // Reserve room for the model even when the controls wrap. Short
              // windows can scroll to every control without shrinking the stage.
              final baseHeight = constraints.maxWidth < 360
                  ? 820.0
                  : compact
                  ? 760.0
                  : 680.0;
              final columns = _motionColumns(
                constraints.maxWidth - (compact ? 40 : 80),
              );
              final rows = (DashmaruMotion.values.length / columns).ceil();
              final extraRows = (rows - (compact ? 2 : 1)).clamp(0, rows);
              final minimumHeight =
                  baseHeight + extraRows * (compact ? 70 : 84);
              return constraints.maxHeight < minimumHeight
                  ? SingleChildScrollView(
                      child: SizedBox(height: minimumHeight, child: content),
                    )
                  : content;
            },
          ),
        ),
      ),
    ),
  );

  Widget _header(bool compact, bool tight) => Row(
    crossAxisAlignment: CrossAxisAlignment.end,
    children: [
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const FlutterLogo(size: 18),
                const SizedBox(width: 8),
                Flexible(
                  child: Text(
                    'FLUTTERKAIGI  /  DASHMARU 3D',
                    style: TextStyle(
                      fontSize: compact ? 10 : 11,
                      color: _green,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.6,
                    ),
                  ),
                ),
              ],
            ),
            SizedBox(height: tight ? 8 : 12),
            Text(
              'だしゅまる、3Dになる。',
              style: TextStyle(
                fontSize: compact ? 29 : (tight ? 36 : 42),
                fontWeight: FontWeight.w800,
                color: _ink,
                letterSpacing: -1.5,
                height: 1.2,
              ),
            ),
            if (!tight) ...[
              const SizedBox(height: 8),
              const Text(
                'Flutter で描く、小さなともだち。',
                style: TextStyle(fontSize: 14, color: _muted),
              ),
            ],
          ],
        ),
      ),
      if (!compact)
        Padding(
          padding: const EdgeInsets.only(bottom: 3),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: Colors.white,
              border: Border.all(color: _line),
              borderRadius: BorderRadius.circular(30),
            ),
            child: const Padding(
              padding: EdgeInsets.symmetric(horizontal: 17, vertical: 10),
              child: Row(
                children: [
                  Icon(Icons.view_in_ar_rounded, size: 17, color: _green),
                  SizedBox(width: 8),
                  Text(
                    'Flutter Scene',
                    style: TextStyle(
                      color: _ink,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
    ],
  );

  Widget _stage(bool compact) => Container(
    clipBehavior: Clip.antiAlias,
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(28),
      border: Border.all(color: _line),
      gradient: _world.background.gradient,
    ),
    child: Stack(
      children: [
        Positioned.fill(
          child: _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: SelectableText(
                      '3D モデルを読み込めませんでした。\n$_error',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: _world.background.inkColor),
                    ),
                  ),
                )
              : !_ready
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CircularProgressIndicator(
                        color: _world.background.inkColor,
                        strokeWidth: 2,
                      ),
                      const SizedBox(height: 18),
                      Text(
                        'だしゅまるを呼んでいます…',
                        style: TextStyle(color: _world.background.inkColor),
                      ),
                    ],
                  ),
                )
              : Semantics(
                  label:
                      'だしゅまるの3Dモデル。${_world.motion.label}のアニメーション。'
                      '${_world.expressionDescription}',
                  child: MouseRegion(
                    cursor: SystemMouseCursors.grab,
                    child: Listener(
                      onPointerSignal: (event) {
                        if (event is PointerScrollEvent) {
                          setState(() => _world.zoom(event.scrollDelta.dy));
                        }
                      },
                      child: GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onPanUpdate: (details) => setState(
                          () => _world.drag(details.delta.dx, details.delta.dy),
                        ),
                        child: scene.SceneView(
                          _world.sceneGraph,
                          cameraBuilder: _world.camera,
                          onTick: _world.tick,
                        ),
                      ),
                    ),
                  ),
                ),
        ),
        Positioned(
          top: 22,
          left: 24,
          child: IgnorePointer(
            child: Row(
              children: [
                Container(
                  width: 7,
                  height: 7,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _ready
                        ? _world.background.inkColor
                        : _world.background.mutedColor,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  _ready
                      ? (_world.playing
                            ? 'LIVE  /  ${_world.motion.label}'
                            : 'PAUSED')
                      : 'LOADING',
                  style: TextStyle(
                    color: _world.background.inkColor,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.2,
                  ),
                ),
              ],
            ),
          ),
        ),
        if (!compact)
          Positioned(
            top: 20,
            right: 24,
            child: IgnorePointer(
              child: Text(
                'ドラッグで回転 · スクロールでズーム',
                style: TextStyle(
                  fontSize: 11,
                  color: _world.background.mutedColor,
                ),
              ),
            ),
          ),
        Positioned(
          bottom: 14,
          left: compact ? 8 : 16,
          right: compact ? 8 : 16,
          child: Row(
            children: [
              _cameraControls(compact),
              const Spacer(),
              if (compact)
                IconButton(
                  tooltip: 'リセット',
                  icon: const Icon(Icons.restart_alt_rounded),
                  color: _world.background.inkColor,
                  onPressed: _ready ? _reset : null,
                )
              else
                _toolButton(
                  icon: Icons.restart_alt_rounded,
                  label: 'リセット',
                  onPressed: _ready ? _reset : null,
                ),
            ],
          ),
        ),
      ],
    ),
  );

  Widget _cameraControls(bool compact) => DecoratedBox(
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: 0.88),
      border: Border.all(color: _line),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Padding(
      padding: const EdgeInsets.all(3),
      child: Row(
        children: [
          for (final preset in [('front', '正面'), ('side', '横'), ('back', '後ろ')])
            TextButton(
              style: TextButton.styleFrom(
                foregroundColor: _ink,
                minimumSize: Size(compact ? 40 : 52, 36),
                padding: EdgeInsets.symmetric(horizontal: compact ? 8 : 12),
                textStyle: const TextStyle(fontSize: 12),
              ),
              onPressed: _ready
                  ? () => setState(() => _world.setCamera(preset.$1))
                  : null,
              child: Text(preset.$2),
            ),
          const SizedBox(height: 18, child: VerticalDivider(width: 8)),
          IconButton(
            tooltip: '自動で回転',
            icon: Icon(
              Icons.threesixty_rounded,
              color: _world.orbiting ? _green : _muted,
              size: 21,
            ),
            isSelected: _world.orbiting,
            onPressed: _ready
                ? () => setState(() => _world.orbiting = !_world.orbiting)
                : null,
          ),
        ],
      ),
    ),
  );

  Widget _motionControls(bool compact) => LayoutBuilder(
    builder: (context, constraints) {
      final columns = _motionColumns(constraints.maxWidth);
      final spacing = compact ? 6.0 : 10.0;
      final width = (constraints.maxWidth - spacing * (columns - 1)) / columns;
      return Wrap(
        spacing: spacing,
        runSpacing: spacing,
        children: [
          for (final motion in DashmaruMotion.values)
            SizedBox(
              width: width,
              height: compact ? 64 : 74,
              child: Tooltip(
                message:
                    '${motion.caption}（キー ${_motionShortcuts[motion.index].$2}）',
                child: _motionCard(motion, compact || width < 120),
              ),
            ),
        ],
      );
    },
  );

  Widget _motionCard(DashmaruMotion motion, bool compact) {
    final active = _world.motion == motion;
    final icon = switch (motion) {
      DashmaruMotion.walk => Icons.directions_walk_rounded,
      DashmaruMotion.jump => Icons.arrow_upward_rounded,
      DashmaruMotion.wave => Icons.waving_hand_rounded,
      DashmaruMotion.blink => Icons.visibility_rounded,
      DashmaruMotion.idle => Icons.spa_rounded,
      DashmaruMotion.run => Icons.directions_run_rounded,
      DashmaruMotion.shake => Icons.sync_alt_rounded,
      DashmaruMotion.sit => Icons.airline_seat_legroom_extra_rounded,
      DashmaruMotion.nod => Icons.check_circle_outline_rounded,
      DashmaruMotion.tilt => Icons.help_outline_rounded,
      DashmaruMotion.bow => Icons.volunteer_activism_rounded,
      DashmaruMotion.celebrate => Icons.celebration_rounded,
      DashmaruMotion.stretch => Icons.self_improvement_rounded,
    };
    return Material(
      color: active ? _green : Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: active ? _green : _line),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: _ready ? () => _selectMotion(motion) : null,
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: compact ? 6 : 12,
            vertical: 10,
          ),
          child: Column(
            crossAxisAlignment: compact
                ? CrossAxisAlignment.center
                : CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: compact
                    ? MainAxisAlignment.center
                    : MainAxisAlignment.start,
                children: [
                  Icon(
                    icon,
                    size: compact ? 19 : 23,
                    color: active ? Colors.white : _green,
                  ),
                  if (!compact) ...[
                    const Spacer(),
                    Text(
                      (motion.index + 1).toString().padLeft(2, '0'),
                      style: TextStyle(
                        color: active ? Colors.white60 : _muted,
                        fontSize: 10,
                        letterSpacing: 1,
                      ),
                    ),
                  ],
                ],
              ),
              SizedBox(height: compact ? 5 : 6),
              Text(
                motion.label,
                style: TextStyle(
                  color: active ? Colors.white : _ink,
                  fontWeight: FontWeight.w700,
                  fontSize: compact ? 12 : 14,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _expressionControls() => Wrap(
    spacing: 6,
    runSpacing: 4,
    crossAxisAlignment: WrapCrossAlignment.center,
    children: [
      const Padding(
        padding: EdgeInsets.only(right: 4),
        child: Text('表情', style: TextStyle(color: _muted, fontSize: 12)),
      ),
      for (final expression in DashmaruExpression.values)
        ChoiceChip(
          label: Text(expression.label),
          selected: _world.expression == expression,
          onSelected: _ready ? (_) => _selectExpression(expression) : null,
          showCheckmark: false,
          selectedColor: const Color(0xFFDCEDE0),
          backgroundColor: Colors.white,
          side: BorderSide(
            color: _world.expression == expression ? _green : _line,
          ),
          labelStyle: TextStyle(
            color: _world.expression == expression ? _green : _muted,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 6),
          visualDensity: VisualDensity.compact,
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
      if (_world.motion == DashmaruMotion.jump)
        const Text(
          'ジャンプは空中で羽ばたく間だけ踏ん張る表情',
          style: TextStyle(color: _muted, fontSize: 12),
        ),
    ],
  );

  Widget _backgroundControls() => Wrap(
    spacing: 6,
    runSpacing: 4,
    crossAxisAlignment: WrapCrossAlignment.center,
    children: [
      const Padding(
        padding: EdgeInsets.only(right: 4),
        child: Text('背景', style: TextStyle(color: _muted, fontSize: 12)),
      ),
      for (final background in DashmaruBackground.values)
        ChoiceChip(
          label: Text(background.label),
          avatar: DecoratedBox(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: background.edgeColor,
              border: Border.all(color: background.mutedColor),
            ),
            child: const SizedBox.square(dimension: 15),
          ),
          selected: _world.background == background,
          onSelected: (_) => _selectBackground(background),
          showCheckmark: false,
          selectedColor: const Color(0xFFDCEDE0),
          backgroundColor: Colors.white,
          side: BorderSide(
            color: _world.background == background ? _green : _line,
          ),
          labelStyle: TextStyle(
            color: _world.background == background ? _green : _muted,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 4),
          visualDensity: VisualDensity.compact,
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
    ],
  );

  Widget _footer(bool compact) => Row(
    children: [
      _toolButton(
        icon: _world.playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
        label: _world.playing ? '一時停止' : '再生',
        onPressed: _ready ? _togglePlay : null,
      ),
      const SizedBox(width: 12),
      DropdownButtonHideUnderline(
        child: DropdownButton<double>(
          value: _world.speed,
          borderRadius: BorderRadius.circular(12),
          isDense: true,
          style: const TextStyle(color: _ink, fontSize: 12),
          icon: const Icon(Icons.expand_more_rounded, size: 18, color: _muted),
          items: [
            for (final speed in [0.5, 1.0, 1.5])
              DropdownMenuItem(
                value: speed,
                child: Text('${speed.toStringAsFixed(1)}×'),
              ),
          ],
          onChanged: !_ready
              ? null
              : (value) => setState(() => _world.setSpeed(value!)),
        ),
      ),
      Expanded(
        child: Text(
          compact
              ? '© 2026 FlutterKaigi'
              : 'だしゅまる © 2026 FlutterKaigi  ·  CC BY-NC-ND 4.0',
          textAlign: TextAlign.end,
          overflow: TextOverflow.ellipsis,
          maxLines: 1,
          style: const TextStyle(fontSize: 10, color: _muted),
        ),
      ),
      IconButton(
        tooltip: 'ライセンス',
        icon: const Icon(Icons.info_outline_rounded, size: 18, color: _muted),
        onPressed: () => showLicensePage(
          context: context,
          applicationName: 'だしゅまる 3D',
          applicationLegalese:
              'キャラクター・3Dモデル・アニメーション\n'
              '© 2026 FlutterKaigi / CC BY-NC-ND 4.0\n'
              'ビューアのコード: © 2026 FlutterKaigi / MIT',
        ),
      ),
    ],
  );

  Widget _toolButton({
    required IconData icon,
    required String label,
    required VoidCallback? onPressed,
  }) => TextButton.icon(
    onPressed: onPressed,
    icon: Icon(icon, size: 19),
    label: Text(label),
    style: TextButton.styleFrom(
      foregroundColor: _ink,
      textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      backgroundColor: Colors.white.withValues(alpha: 0.8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ),
  );
}
