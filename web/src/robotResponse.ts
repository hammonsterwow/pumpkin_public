export interface RobotResponseSource {
  robot_response?: string;
}

export function readRobotResponse(source: RobotResponseSource): string {
  return source.robot_response?.trim() || '';
}
