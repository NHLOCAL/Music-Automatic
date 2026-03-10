import React from "react";
import {
  ArrowLeftOutlined, BulbOutlined, CheckCircleOutlined, CheckOutlined,
  ClockCircleOutlined, ClusterOutlined, CloseOutlined, CustomerServiceOutlined,
  DatabaseOutlined, DeleteOutlined, DownOutlined, ExclamationCircleOutlined,
  EyeOutlined, FolderOpenOutlined, InfoCircleOutlined, LineChartOutlined,
  PlusOutlined, SafetyCertificateOutlined, SettingOutlined, StarOutlined, SwapOutlined
} from "@ant-design/icons";

const iconMap = {
  trash: DeleteOutlined, check: CheckOutlined, "check-circle": CheckCircleOutlined,
  folder: FolderOpenOutlined, shield: SafetyCertificateOutlined, alert: ExclamationCircleOutlined,
  music: CustomerServiceOutlined, eye: EyeOutlined, plus: PlusOutlined, x: CloseOutlined,
  settings: SettingOutlined, "chevron-down": DownOutlined, sparkle: StarOutlined,
  layers: ClusterOutlined, compare: SwapOutlined, chart: LineChartOutlined,
  clock: ClockCircleOutlined, database: DatabaseOutlined, info: InfoCircleOutlined,
  "arrow-left": ArrowLeftOutlined, bulb: BulbOutlined,
};

export function Icon({ name, size = 16, className = "", style, onClick }) {
  const Component = iconMap[name] ?? InfoCircleOutlined;
  return <Component className={className} style={{ fontSize: size, ...style }} onClick={onClick} aria-hidden="true" />;
}

export function StatusTag({ tone = "neutral", icon, children, className = "", style }) {
  return (
    <span className={`badge ${tone} ${className}`.trim()} style={style}>
      {icon && <Icon name={icon} size={12} style={{ marginInlineEnd: 4 }} />}
      {children}
    </span>
  );
}