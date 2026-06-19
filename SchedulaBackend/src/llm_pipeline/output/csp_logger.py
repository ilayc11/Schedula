"""
CSP output logger - writes constraints to file
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from ..models.atomic_constraint import AtomicConstraint


class CSPOutputLogger:
    """Logs CSP-ready constraints to file"""
    
    def __init__(self, output_file: str = "CSP_INPUT.json"):
        self.output_file = Path(output_file)
        self.constraints_log: List[Dict[str, Any]] = []
    
    def log_constraint(self, constraint: AtomicConstraint, original_input: str):
        """Log a single constraint to memory"""
        csp_data = constraint.to_csp_format()
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "original_input": original_input,
            "constraint": csp_data
        }
        
        self.constraints_log.append(log_entry)
    
    def write_to_file(self):
        """Write all logged constraints to file"""
        output_data = {
            "generated_at": datetime.now().isoformat(),
            "total_constraints": len(self.constraints_log),
            "constraints": self.constraints_log
        }
        
        with open(self.output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n{'='*80}")
        print(f"📝 CSP INPUT FILE GENERATED")
        print(f"{'='*80}")
        print(f"File: {self.output_file.absolute()}")
        print(f"Total constraints: {len(self.constraints_log)}")
        print(f"{'='*80}\n")
    
    def clear(self):
        """Clear the log"""
        self.constraints_log = []

