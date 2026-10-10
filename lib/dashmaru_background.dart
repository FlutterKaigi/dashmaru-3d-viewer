import 'package:flutter/painting.dart';

/// Presentation colors, independent of the character's materials and lighting.
enum DashmaruBackground {
  mint(
    'ミント',
    Color(0xFFFFFFFF),
    Color(0xFFEAF1E5),
    Color(0xFF287757),
    Color(0xFF52685E),
    (0.77, 0.87, 0.79),
  ),
  studio(
    'スタジオ',
    Color(0xFFFFFFFF),
    Color(0xFFE9EDF3),
    Color(0xFF445D79),
    Color(0xFF56687D),
    (0.81, 0.85, 0.91),
  ),
  peach(
    'ピーチ',
    Color(0xFFFFFCF7),
    Color(0xFFF6DCD2),
    Color(0xFF8F5148),
    Color(0xFF805A53),
    (0.93, 0.77, 0.70),
  ),
  night(
    '夜',
    Color(0xFF344D6B),
    Color(0xFF17283F),
    Color(0xFFE0F4F1),
    Color(0xFFB7C9DB),
    (0.22, 0.31, 0.44),
  );

  const DashmaruBackground(
    this.label,
    this.centerColor,
    this.edgeColor,
    this.inkColor,
    this.mutedColor,
    this.plinthColor,
  );

  final String label;
  final Color centerColor;
  final Color edgeColor;
  final Color inkColor;
  final Color mutedColor;

  /// Linear RGB, matching the physically based material's color space.
  final (double, double, double) plinthColor;

  RadialGradient get gradient => RadialGradient(
    center: const Alignment(0, -0.4),
    radius: 1.1,
    colors: [centerColor, edgeColor],
  );

  static DashmaruBackground parse(String? value) => values.firstWhere(
    (background) => background.name == value?.toLowerCase(),
    orElse: () => mint,
  );
}
