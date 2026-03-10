import React from "react";
import {
  ArrowLeftOutlined,
  BulbOutlined,
  CaretRightOutlined,
  CheckCircleOutlined,
  CheckOutlined,
  ClockCircleOutlined,
  ClusterOutlined,
  CloseOutlined,
  CustomerServiceOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  DownOutlined,
  ExclamationCircleOutlined,
  EyeOutlined,
  FolderOpenOutlined,
  InfoCircleOutlined,
  LineChartOutlined,
  PictureOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  StarOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import { Tag } from "antd";

const iconMap = {
  trash: DeleteOutlined,
  check: CheckOutlined,
  "check-circle": CheckCircleOutlined,
  folder: FolderOpenOutlined,
  shield: SafetyCertificateOutlined,
  alert: ExclamationCircleOutlined,
  music: CustomerServiceOutlined,
  eye: EyeOutlined,
  plus: PlusOutlined,
  x: CloseOutlined,
  settings: SettingOutlined,
  "chevron-down": DownOutlined,
  sparkle: StarOutlined,
  layers: ClusterOutlined,
  compare: SwapOutlined,
  chart: LineChartOutlined,
  clock: ClockCircleOutlined,
  database: DatabaseOutlined,
  info: InfoCircleOutlined,
  "arrow-left": ArrowLeftOutlined,
  bulb: BulbOutlined,
  play: CaretRightOutlined,
  image: PictureOutlined,
};

const toneColorMap = {
  success: "success",
  warning: "gold",
  danger: "error",
  neutral: "default",
  primary: "processing",
};

export function Icon({ name, size = 18, className = "", style }) {
  const Component = iconMap[name] ?? InfoCircleOutlined;
  return <Component className={className} style={{ fontSize: size, ...style }} aria-hidden="true" />;
}

export function StatusTag({ tone = "neutral", icon, children, className = "", ...props }) {
  return (
    <Tag
      color={toneColorMap[tone] ?? toneColorMap.neutral}
      icon={icon ? <Icon name={icon} size={14} /> : null}
      variant="filled"
      className={`cartoon-tag ${className}`.trim()}
      {...props}
    >
      {children}
    </Tag>
  );
}
