/**
 * sensing.service.ts — ruvnet naming-convention re-export
 * 참조: ruvnet/ui/services/sensing.service.js
 *
 * 실제 구현은 sensingService.ts 에 있습니다.
 * 이 파일은 ruvnet 원본과 동일한 파일명으로 접근하기 위한 배럴입니다.
 */
export {
  sensingService,
  type ConnectionState,
  type DataSource,
  type SensingData,
  type SensingFeatures,
  type SensingClassification,
  type SignalField,
} from './sensingService';
