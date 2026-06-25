export const API_PREFIX = "/api/v1";

export interface PromptData {
  text: string;
  sources: string[];
}

export const PROMPTS: PromptData[] = [
  { text: 'How do I model anisotropic materials in Slide2?', sources: ['ROC'] },
  { text: 'How to create a bond-slip reinforcement in DIANA?', sources: ['ROC', 'DIANA'] },
  { text: 'Does RSLog offer customization?', sources: ['ROC'] },
  { text: 'Can RSWall design for different wall types like MSE or gabion walls?', sources: ['ROC'] },
  { text: 'What is the difference between equal angle and equal area projection?', sources: ['ROC'] },
  { text: 'How do I apply a sloped backfill in RSWall?', sources: ['ROC'] },
  { text: 'Does Dips handle oriented cores?', sources: ['ROC'] },
  { text: 'Can I import Radar data and what is the advantage?', sources: ['ROC'] },
  { text: 'How are horizontal stresses calculated in Settle3?', sources: ['ROC'] },
  { text: 'What is ShapeMetriX used for?', sources: ['ROC', '3GSM'] },
  { text: 'How can I analyze a helical pile in axial lateral analysis?', sources: ['ROC'] },
  { text: 'What is the intelligent search in Slide3? And ROI?', sources: ['ROC'] },
  { text: 'How do I define groundwater conditions using FEA seepage analysis?', sources: ['DIANA', 'ROC'] },
  { text: 'How to define coupled flow-stress analysis?', sources: ['DIANA'] },
  { text: 'How can I apply both a fill load and a staged embankment load in Settle3?', sources: ['ROC'] },
  { text: 'Can I use the zoning and pile capacity table generator for driven piles?', sources: ['ROC'] },
  { text: 'Can I import my gINT data into RSLog?', sources: ['ROC'] },
  { text: 'How can ShapeMetriX be used in mining?', sources: ['ROC', '3GSM'] },
  { text: 'How can I create a wrapped set using the freehand set window option?', sources: ['ROC'] },
  { text: 'What design standards are provided in RSWall?', sources: ['ROC'] },
  { text: 'What is the spatial variability analysis in Slide2?', sources: ['ROC'] },
];